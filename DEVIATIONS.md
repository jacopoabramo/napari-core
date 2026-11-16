# Deviations from the target architecture

napari-core is a prototype of a core library for napari-like viewers, written
against a target architecture to find out whether that design holds once code
is written to it. The prototype shows one layer type, `Image`, in two
dimensions, slices it synchronously from an array of any number of dimensions,
and draws it with one backend, vispy. This file lists each place where the
code differs from the target's rules (section 1), its package map (section 2)
and its interfaces (sections 3.1 to 3.5), and each place where the target says
nothing and the prototype had to decide. Each entry says what the target says,
what the code does and why, and ends with a recommendation: change the target,
change the prototype later, or change neither.

Section numbers and names are those of the target architecture document. Parts
of the target that the prototype leaves out on purpose (three-dimensional
display, multiscale data, asynchronous slicing, key events, commands, plugins,
feature tables, the pygfx backend and the `napari_core.app` package) are named
only where leaving them out changes something else. The behaviour described
here is that of the code with numpy 2.4.6, psygnal 0.16.1, pydantic 2.14.3,
dask 2026.8.0 and vispy 0.17.0, checked by pyright and pyrefly in strict mode.

## Summary

Six findings matter most for the target, because each is a place where the
target is wrong or incomplete.

The package order of section 2 does not hold. `napari_core.interaction` turns
surface events into input events, so it has to import the surface event types
and the `RenderSurface` protocol from `napari_core.render`, and `render`
therefore sits below `interaction` rather than above it.

Rule 8 makes psygnal's `EventedModel` the base of every model, and four of
psygnal's behaviours needed workarounds in the prototype, three of them clear
candidates for a change in psygnal. psygnal's field signals also carry no
argument types, so no connection the core makes to a model signal is checked
by a type checker, which rule 9 asks for.

A field that holds a component, and a layer's `data`, must compare by identity.
With psygnal's default equality, assigning a component equal to the old one
emits nothing, so a renderer stays connected to the replaced object and stops
following the layer. Section 3.2 says nothing about how fields compare.

The `LayerAdapter` protocol of section 3.4 has a constructor typed with
`Layer`, and a strict type checker rejects an adapter whose constructor takes
an `Image` against it. The prototype registers a factory typed with the layer
type instead. The protocol also gives an adapter no way to reach the surface
it draws on, which the vispy adapter needs.

Rule 9 cannot be met by a backend built on a library without type information
unless the checker's rules about unknown types are relaxed in the backend's
own files. The vispy backend relaxes four pyright rules in two files, and has
two casts and two pyrefly line suppressions.

A render surface lives only as long as something holds a reference to it, and
the core cannot close it when its window closes without importing a GUI
toolkit. The front end therefore has to call `surface.close()`, and the
`FrontEnd` protocol of section 3.6 says nothing about a surface's lifetime yet.

## 1. Principles

### Rules 4 and 8: signals are psygnal's `.events`, without type checking

Rule 4 makes every state change a psygnal signal and keeps napari's `.events`
surface as a compatibility layer that wraps psygnal emissions in napari
`Event` objects. Rule 8 makes every model a psygnal `EventedModel`, and rule 9
asks for complete annotations.

In the prototype every model is a psygnal `EventedModel`: `Dims`, `Camera`,
`Colormap`, `Transform`, `IntensityAppearance`, `Layer`, `Image`, `View` and
`ViewerModel`, all in `napari_core.model`. Their only signal surface is
psygnal's own `.events`, with no compatibility layer, and the core connects
through it like any other code. The one signal that is not a model field,
`Slicer.sliced`, is a psygnal `Signal(Layer)`. None of these connections is
type-checked: `layer.events.visible` is a plain `SignalInstance`, so a slot of
any signature passes both checkers.

The compatibility layer is left out because nothing in the prototype has
napari's old callbacks to serve. The connections are unchecked because no
psygnal release gives a signal argument types. Typing a signal declared on a
class, such as `Slicer.sliced`, is a smaller change to psygnal than typing the
field signals of an `EventedModel`, because psygnal creates the field signals
from the fields at run time.

Recommendation: change the target. Rule 9 should say that connections to
model signals stay unchecked until psygnal types its field signals, and that
this needs a change to psygnal beyond typed class-level signals.

### Rule 8: psygnal behaviours the prototype works around

Four behaviours of psygnal 0.16.1 needed a workaround. The last is a side
effect of psygnal's evented list and the least certain of them.

| Behaviour | Workaround in the prototype | Candidate for a change in psygnal |
|---|---|---|
| A field with no entry in `field_dependencies` emits the value as it was assigned, before validation, and compares that raw value with the old one. Assigning `2` to a float field emits the integer `2`, and assigning a colormap name emits the string. | The field lists itself in `field_dependencies`: `Camera.center`, `Camera.zoom`, `Dims.current_step`, `IntensityAppearance.colormap`, and `Layer.name`, `visible` and `opacity`. psygnal's path for fields with dependents reads the stored value back after validation and emits only when it differs. pydantic's `ConfigDict` has no `field_dependencies` key, so both checkers reject it, and `EventedConfigDict` in `napari_core.model` adds the key. A field listing itself is not documented psygnal behaviour. | Yes: emit the validated value on every path, and export a configuration type that has `field_dependencies`. |
| psygnal's metaclass replaces an `__eq_operators__` dictionary set in the class body with one it builds from the annotations, and builds it again for every subclass, so an entry set on a base class does not reach its subclasses. | The metaclass `LayerMeta` of `Layer` sets identity comparison after psygnal has built the dictionary: for every field annotated with an evented model or a union holding one, and for every name in the class variable `compared_by_identity` of the class and its bases (`Image` lists `data`). A pydantic hook or `__init_subclass__` runs before psygnal resets the dictionary, so only a metaclass can do it. | Yes: honour a declared `__eq_operators__` and inherit it from the base class. |
| `SignalInstance.disconnect` annotates its slot as a bare `Callable`, so strict pyright reports `Type of "disconnect" is partially unknown` (`reportUnknownMemberType`) at every call. | The core never calls `disconnect`. Each group of connections is a set of bound methods of one small object (`_Follower` in the slicer; `Reactions`, `AppearanceReactions`, `TransformReactions` and `ViewSync` in the vispy backend). psygnal holds bound methods weakly, so dropping the object disconnects all of them. This relies on the object being freed as soon as its last reference goes, as CPython's reference counting does. | Yes: annotate the slot completely. |
| An `EventedList` built with its default `child_events=True` connects every signal of each inserted item, and with pydantic 2.14.3 inserting a layer emits pydantic's `PydanticDeprecatedSince211` warning. | `View.layers` is built with `child_events=False`, also when a list is passed to the constructor. | Possibly; the cause inside psygnal was not investigated. |

Recommendation: change neither for now. The workarounds are small, and each
can go once psygnal changes.

### Rule 9: strict typing, and a backend on an untyped library

Rule 9 asks for complete annotations without `Any`, strict checking with no
excluded file and with pyrefly's `bad-override-mutable-attribute` check on,
and `object` only where a value can be anything.

`Any` appears nowhere in the core's own annotations, and pyright and pyrefly
both run in strict mode over the whole package with no excluded file; the
package ships `py.typed`. pyrefly needs its `strict` preset set in the project
configuration, because without a preset it accepts a function with no
annotations at all. Its strict preset reports `bad-override-mutable-attribute`.
`object` is used for the argument of `as_layer_data` before it is checked, for
the result of indexing layer data (section 3.1), and where the type does not
matter to the code, such as the native type in
`attach(view, surface: RenderSurface[object])`.

The vispy backend in `napari_core.render.vispy` is the exception. vispy ships
no type information, so both checkers report unknown types on every vispy
call, and the backend relaxes the checkers as listed here, in its own files
only:

| File | Relaxation |
|---|---|
| `_image.py` | pyright, file comment: `reportMissingTypeStubs`, `reportUnknownMemberType`, `reportUnknownVariableType`, `reportUnknownArgumentType` set to false |
| `_image.py` | `cast(Visual, ImageVisual(interpolation="nearest"))`, because both checkers see only the visual half of vispy's scene node; `Visual` is a protocol of the parts the adapter uses |
| `_surface.py` | pyright, file comment: the same four rules set to false |
| `_surface.py` | `cast(NativeT, self._canvas.native)`, because vispy leaves the native widget unannotated |
| `_surface.py` | pyrefly, line: `# pyrefly: ignore[bad-argument-type]` on the `parent` argument of `SceneCanvas`, which pyrefly infers as vispy's own widget type |
| `_surface.py` | pyrefly, line: `# pyrefly: ignore[missing-attribute]` on `self._canvas.events`, which vispy sets in a base class constructor that pyrefly does not follow |
| `_backend.py`, `__init__.py` | none |

A type error in the backend's own use of vispy is therefore not found
statically; the backend's tests, which draw and take screenshots, carry that.

Recommendation: change the target. Rule 9 should allow a backend built on a
library without type information to relax the unknown-type rules in its own
modules, and require the relaxations to be listed per file. The alternative is
to write stubs for the parts of the library a backend uses, which the
`Visual` protocol already does for one vispy class.

## 2. Package map

### `render` sits below `interaction`

The target's table orders the core packages `typing`, `data`, `model`,
`interaction`, `render`, and a package may import only those above it.

The prototype orders them `typing`, `data`, `model`, `render`, `interaction`,
and an import-linter contract enforces it. `attach(view, surface)` in
`napari_core.interaction` takes a `RenderSurface` and handles the surface
event types, both defined in `napari_core.render`, so `interaction` has to
import `render`. Nothing in `render` needs `interaction`. The vispy backend
imports neither `interaction` nor `data`.

The table's row for the backends also says a backend translates input "into
the model's event types", while section 3.4 has a backend emit surface events
that `interaction` then turns into the model's input events. The prototype
follows section 3.4: the vispy surface emits surface events only.

Recommendation: change the target. Swap the rows of `interaction` and
`render`, and say in the backends' row that a backend emits surface events.

### What each package imports

The target lists what each package may import besides the packages above it.
The prototype's packages import the following, which the import-linter
contracts and a test that imports the core in a fresh interpreter (and finds
no vispy, Qt or dask module loaded) keep in place:

| Package | Core packages it imports | Other libraries |
|---|---|---|
| `napari_core.typing` | none | numpy, typing-extensions |
| `napari_core.data` | `typing` | numpy, typing-extensions; dask only under `TYPE_CHECKING` |
| `napari_core.model` | `typing`, `data` | psygnal, pydantic, numpy, typing-extensions |
| `napari_core.render` | `model` | numpy |
| `napari_core.interaction` | `model`, `render` | none |
| `napari_core.render.vispy` | `typing`, `model`, `render` | vispy, numpy |

Two details differ from the target. typing-extensions is imported by three
packages (for `TypeVar` with a default, `TypeIs` and `override`) but appears in
no row of the target's table, although section 3.1 itself needs it for the
default of `DTypeT_co` before Python 3.13. And the dask adapter never imports
dask at run time: it recognises a dask array by the module name of its type
and turns a slice into NumPy with `np.asarray`, which goes through dask's own
`__array__`.

The target also asks for a contract that forbids importing a package's private
modules from outside the package. The prototype has only three contracts (the
package order, no Qt binding anywhere in the core, vispy only in the vispy
backend), and two test fixtures reach the private adapter registries by their
module paths.

Recommendation: change the target to list typing-extensions as a core
dependency every package may import. Change the prototype later to add the
contract on private modules.

### No `napari_core.app`

The target puts the front-end protocol, the registry of open viewers, the
slicing executor and the hand-off to the main thread in `napari_core.app`, and
offers `register_backend` in `napari_core.render`.

The prototype has no `napari_core.app` and no backend registry. Its example,
which plays the front end, builds a `ViewerModel`, makes a surface with
`VispyBackend[QWidget]().create_surface(view, None)`, connects the two with
`attach(view, surface)` and puts `surface.native` in a Qt window. The package
is left out because most of what the target puts there serves app-model, key
dispatch or asynchronous slicing, none of which the prototype has.

The example shows a gap the target does not cover: showing a view takes two
calls, one that makes the surface and one that attaches it to the view, and
the target names no package that makes the second.

Recommendation: change the target. Section 3.6 should say which side attaches
a surface to its view when a front end hosts it.

## 3.1 Layer data

### The one-member protocols and their two deliberate differences

The target composes `LayerDataProtocol` from protocols of one member each,
named as array-api-typing names them: `HasDType` copied from that package, and
`HasShape`, `HasNDim`, `HasSize` and `HasGetItem` written in the form of its
open pull requests.

The prototype does this in `napari_core.typing`, which exports all five along
with `DTypeT_co`, `BasicKey`, `SliceArray` and `LayerDataProtocol`. `HasDType`
is copied with its MIT notice; `HasShape`, `HasNDim` and `HasSize` follow pull
request 34 and `HasGetItem` follows pull request 69. Two differences from
those pull requests are deliberate. `shape` is `tuple[int, ...]` and `size` is
`int`, where the pull requests allow `None` for a dimension of unknown size,
because layer data must have known sizes (see the entry on dask below). And
`__getitem__` returns `object` where pull request 69 returns `Self`, which the
next entry explains. The key of `__getitem__` is positional-only, as in the
pull request, because numpy's `__getitem__` has a positional-only key and both
checkers reject `np.ndarray` against a protocol whose key may be passed by
name. The target's flat listing shows the key as an ordinary parameter.

Recommendation: change the target to state the two differences and the
positional-only key, so that the protocols can become imports from
array-api-typing once it releases them, with the differences kept as
napari's own narrowing.

### `__getitem__` returns `object`

The target's `LayerDataProtocol.__getitem__` returns
`LayerDataProtocol[DTypeT_co]`.

The prototype's returns `object`. Only an array's own adapter indexes layer
data (in `ArrayAdapter.materialize`), and the adapter knows its library's
types, so no code in the core reads the result through the protocol. A precise
result type only excludes arrays: in a check with pyright and mypy against
zarr 3.4.2, made before the code was written, a zarr `Array` failed a protocol
whose `__getitem__` returns `Self`, because indexing it returns a NumPy array.
This was not checked again; zarr is not installed in the prototype's
environment.

Recommendation: change the target to return `object`.

### The default of the dtype parameter

The target's `DTypeT_co` defaults to `object`.

The prototype's defaults to `np.dtype[np.generic]`, the type of any NumPy
dtype, so the bare name `LayerDataProtocol` means an array with a NumPy dtype.
With a default of `object`, `data.dtype.kind` is a type error, and every
reader of the dtype would have to narrow it first. NumPy and dask report NumPy
dtypes, and an array library with a dtype class of its own writes that class
in the brackets. A static test checks that `data.dtype` of bare layer data is
`np.dtype[np.generic]` to both checkers.

Recommendation: change the target.

### `as_layer_data` in place of `assert_protocol`

The target checks layer data once, on assignment, with `assert_protocol`,
which raises a `TypeError` naming the missing members.

The prototype's `napari_core.data.as_layer_data(obj: object) -> LayerDataProtocol`
does the same check and returns its argument typed as layer data, so typed
code starts from the value it returns. It also checks what a member check
cannot: that `dtype` is a NumPy dtype and that every entry of `shape` is a
Python `int`. It raises `TypeError` in every case. `Image.data` is checked by
a field validator that calls it, and pydantic reports the error as a
`ValidationError`.

Recommendation: change the target to a function that returns the checked
value.

### dask arrays: not layer data to a type checker, and unknown sizes refused

The target does not say how a dask array meets the protocol.

dask annotates `shape` as `tuple[int | float, ...]` and `size` as
`int | float`, with a float for the NaN of an unknown chunk size, so neither
checker accepts a dask array as `LayerDataProtocol` (a static test asserts
this). A dask array enters the core through `as_layer_data`, like any other
value from outside, and the checkers then see the protocol. A dask array whose
chunk sizes are unknown, such as the result of a boolean mask, fails the check
on `shape`, and the error message says to call `compute_chunk_sizes()` first.

Recommendation: change the target to say that layer data has known sizes and
that dask arrays enter through `as_layer_data`.

### The array adapter has three members

The target's `ArrayAdapter` has `in_memory`, `accepts`, `materialize`,
`reduce`, `chunk_shape` and `slicing_context`, and the dask adapter brings
dask's cache and the switch that turns task fusion off around a slice.

The prototype's `ArrayAdapter` in `napari_core.data` has `in_memory`,
`accepts` and `materialize`, because slicing a plane needs nothing more. The
NumPy adapter accepts instances of `np.ndarray` only and the dask adapter
accepts any value whose type comes from a module of the `dask` package; it has
no cache and no fusion switch. Both are registered when `napari_core.data` is
imported. Besides `register_array_adapter`, the package exports
`adapter_for(data)`, which returns the first adapter, by priority, that
accepts the data, and raises `TypeError` when none does. The contrast limits
of an image are read through `materialize`, not `reduce` (section 3.2).

`WritableLayerDataProtocol`, `SupportsDLPack`, `MultiscaleLayerData`,
`ScalarFieldData` and the feature table are not built, and `SliceArray` is
`npt.NDArray[np.generic]` alone, because the prototype has no writes, no
device arrays, no multiscale data and no features.

Recommendation: change neither; the missing members belong to later stages.
The target could list `adapter_for` as the lookup function of the registry.

## 3.2 Layers built from components

### Layers declare their components as fields

The target declares a layer as a psygnal `EventedModel` whose fields are its
state, with components as fields, and replaces an earlier `LayerComponents`
holder with them.

The prototype follows this and has no holder. `Layer` has the fields `name`,
`visible`, `opacity` and `transform`; `Image` adds `data` and `appearance`.
`Transform` has only `scale` and `translate`, and `IntensityAppearance` has
`colormap`, `contrast_limits` and `gamma`; the other fields of the target's
components belong to three dimensions or to features the prototype leaves
out. `Colormap` is a model of its own with a name and an RGBA table, and
`COLORMAPS` holds five built-in ones (`gray`, `red`, `green`, `blue`,
`magenta`). Assigning a name to a colormap field looks it up there. The names
napari users know are properties on `Image` that read and write the
components: `colormap`, `contrast_limits`, `gamma`, `scale` and `translate`.

Recommendation: change neither. Declaring components as fields worked for
`Image`, for the vispy adapter that follows them and for layer subclasses,
once they were compared by identity (next entry).

### Components and `data` compare by identity

The target does not say how a field compares its old and new values.

psygnal emits a field's signal only when the new value differs from the old
one, and by default it compares with `==`. For a component this is wrong. A
renderer that draws a layer connects to the signals of the layer's current
`appearance` and `transform` objects. When a caller assigns a new component
that happens to equal the old one, psygnal emits nothing, so the renderer
stays connected to the old object: later changes to the new component are not
drawn, and changes to the discarded one still are. For `data`, psygnal falls
back to `np.array_equal`, which compares two arrays element by element on
every assignment and would compute a dask array in full.

The prototype therefore compares these fields by identity: every field of a
`Layer` subclass annotated with an evented model, or with a union that holds
one such as `Transform | None`, and every name the class lists in
`compared_by_identity`, which `Image` uses for `data`. A container of
components, such as `list[Transform]`, keeps comparing by contents, because it
is changed in place rather than replaced. Assigning an equal but distinct
component now emits once, with the new object. The metaclass that sets this up
is described under rule 8.

Recommendation: change the target. Section 3.2 should say that component
fields and data fields compare by identity, for every layer type, including
those a plugin adds.

### `Layer` is abstract, and what it leaves out

The target's `Layer` has `blending`, `mode`, `loaded`, four callback lists,
`refresh`, `get_value` and `make_slice_request`, and does not say which
members a layer type must supply.

The prototype's `Layer` cannot be instantiated: a layer type implements
`ndim`, `extent_steps` (the number of steps on each of its axes) and
`slice(dims)`, which returns the displayed plane as a NumPy array. `Layer`
itself provides `slice_key(dims)`, the basic key of the displayed plane; it
aligns the layer's axes with the last axes of the dims and raises
`ValueError` when the layer has more axes than the dims. `blending`, `mode`,
`loaded`, `refresh`, `get_value` and `make_slice_request` are absent, because
nothing in the prototype uses them.

Recommendation: change the target to name the members a layer type must
implement. The absent members belong to later stages.

### The callback lists take `Self`

The target types the callback lists with `Layer`, as
`list[MouseCallback['Layer']]`.

The prototype's `mouse_drag_callbacks` and `mouse_wheel_callbacks` are
read-only properties over private attributes, and their callbacks take
`Self`. With `Layer`, both checkers reject `def on_drag(layer: Image, event:
ButtonEvent)` on an image's list, because a callable's parameters are
contravariant; with `Self`, a callback written for an `Image` joins an
`Image`'s list, and one written for another layer type is rejected (both cases
are in the static tests). The lists are not fields because pydantic refuses a
public attribute that is not a field, and a field would validate and emit on
every assignment for no reader. The move and double-click lists are absent.

Recommendation: change the target to type the callback lists with `Self`.

### An `Image` keeps its number of dimensions

The target does not say what happens when an image's data is replaced by an
array with another number of dimensions.

The prototype refuses it. An `Image` checks that its transform has one scale
and one translation per axis of its data, when it is built and on every
assignment of `data` or `transform`. An assignment that breaks this raises
pydantic's `ValidationError`, a `ValueError`, keeps the old value and emits
nothing. Changing the number of dimensions atomically would need `data` and
`transform` assigned together, which psygnal's per-field assignment cannot
express, so a caller who wants another number of dimensions makes a new layer.
Assigning to `transform.scale` directly is not checked (see the last section).

Recommendation: change the target to decide this, either as the prototype
does or with an operation that replaces data and transform together.

### Defaults and contrast limits of an `Image`

The target does not give an image's defaults, and puts the whole-array minimum
and maximum on the adapter's `reduce`.

An `Image` built without a transform gets scale 1.0 and translation 0.0 on
every axis of its data. Built without an appearance, it gets the `gray`
colormap, gamma 1.0, and contrast limits from `reset_contrast_limits()`. That
method reads data whose adapter says `in_memory` in full, and other data only
at the middle step of every axis except the last two, so that a dask array is
not computed whole. It ignores values that are not finite, uses `(0.0, 1.0)`
when no finite value is left, and widens the range to `(low, low + 1.0)` when
all values are equal. A constant image of 255 therefore gets `(255.0, 256.0)`
and is drawn black.

Recommendation: change the target to say where default contrast limits come
from for lazy data. Change the prototype later to compute the in-memory case
through `reduce` once adapters have it, since the current code copies the
finite values of the whole array.

## 3.3 Slicing

### `Dims`: `nsteps`, `displayed` as a property, and fitting to `ndim`

The target uses `Dims` without listing its fields, apart from
`Dims.current_step`.

The prototype's `Dims` has `ndim` (at least 2), `nsteps`, the number of steps
on each axis, and `current_step`, one integer per axis. `nsteps` exists
because a slider needs its range. `displayed` is a read-only property,
`(ndim - 2, ndim - 1)`, so that it cannot disagree with `ndim`. `nsteps` and
`current_step` always have one entry per axis: growing `ndim` pads them on the
left, shrinking it drops entries from the left, and `current_step` is clamped
to each axis. A tuple of the wrong length assigned to either is fitted the same
way without an error, so a caller must set `ndim` first, or an axis is lost.

Recommendation: change the target to give `Dims` these fields and the rule for
a change of `ndim`.

### `Dims` counts data steps, and world coordinates are `(row, column)`

The target maps a layer's axes onto world axes through its transform, and does
not fix the order of the world coordinates of the displayed plane.

World coordinates are `(row, column)`, as in napari: surface `y` maps to world
axis 0, surface `x` to world axis 1, and `Camera.center` is `(row, column)`.
Pixel `(i, j)` of an image is centred on world point `(i, j)` times the
layer's scale plus its translation. The transform is applied to the two
displayed axes only. On every other axis, `Dims` counts the steps of the
layers' data: `nsteps` is the largest extent among the layers on each axis,
aligned to the last axis, and `current_step` is used as an index into each
layer's data. Two layers with different scales on a sliced axis are therefore
aligned by index, not by world position.

Recommendation: change the prototype later, when a second layer type or a
non-unit scale on a sliced axis needs world positions there. The target
should then say how a step of `Dims` relates to world coordinates.

### The slicer belongs to the view and fits the dims

The target gives each view a `Slicer` that runs slice requests and keeps the
latest response per layer, and does not say who sets the dims from the
layers.

The prototype's `Slicer(dims, layers)` belongs to its `View`, which creates it
and exposes it through a read-only `slicer` property. It also fits the dims to
the layers: `ndim` is the largest number of axes among them, at least 2, and
`nsteps` the largest extent on each axis. It refits when the layer list
changes and when a layer's `data` is replaced, sets `ndim` before `nsteps`, and
emits `sliced` only after the dims are fitted, so a listener never sees dims
that do not fit the layer. It slices a layer when it joins the list and when
its data is replaced, and every layer when `current_step` changes. One layer
can be in two views and has its own slice in each. The layers' signals hold the
slicer's connections weakly, so a view is freed while its layers live on.

Recommendation: change the target to give the slicer the fitting of the dims,
since it is the part that already listens to the layer list and to data
changes.

### Synchronous slicing with no request or response types

The target slices through `Layer.make_slice_request(dims, view_state)`, with
`SliceRequest`, `SliceResponse` and `ViewState` types, an executor, and
`slice_failed`, `sync_slicing` and `wait_until_idle`.

The prototype slices synchronously on the calling thread, through
`Layer.slice(dims)`, and has none of these types or members.
`Slicer.response(layer)` returns the last slice as a NumPy array, or `None`
for a layer the slicer does not follow, and `Slicer.sliced` emits the layer
whose slice changed, one layer at a time, as the target's per-layer delivery
asks. The whole displayed plane is sliced, with no culling to what the camera
shows. Synchronous slicing for a core without `napari_core.app` is what the
target itself describes.

Recommendation: change neither. The `sliced` signal and `response` were all the
backend needed for one image; the request types belong to the stage that adds
asynchronous slicing.

### `View` and `ViewerModel`

The target's `View` holds dims, a `Scene` with the camera, a `Canvas` model
with the size and grid, a cursor, a layer list and a slicer, and a
`ViewerModel` holds one or more views.

The prototype's `View` has `dims`, `camera`, `canvas_size` (logical pixels,
`(640, 480)` until a surface reports its size) and `layers`, a psygnal
`EventedList` that does not re-emit its layers' events. `dims` and `layers`
cannot be replaced, because the slicer holds them. `View(layers=[...])` builds
a new list from the items, refuses an item that is not a `Layer`, and slices
each layer; an existing `EventedList` passed in is copied, not adopted, so
later changes to the caller's list do not reach the view. `ViewerModel` holds
one `view` and reads its `layers`, `dims` and `camera` through properties.
There is no `Scene`, `Canvas` model, cursor or grid.

Recommendation: change neither for the missing parts. The target should say
that the layer list does not re-emit its layers' events (rule 8 table).

## 3.4 Model to renderer

### No render views or view builders

The target dropped a frozen render view per layer type in favour of a backend
that reads the layer's public fields and takes the slice from the view.

The prototype does the same, and needed nothing more. The vispy image adapter
connects to `layer.events.visible` and `opacity`, to the appearance's
`colormap`, `contrast_limits` and `gamma`, to the transform's `scale` and
`translate`, to `layer.events.appearance` and `transform` to follow a
replaced component, and to `view.slicer.sliced` for new pixel data.

Recommendation: change neither.

### A layer adapter is registered as a factory

The target's `LayerAdapter` protocol has `__init__(self, layer: Layer, view:
View)` and `close()`, and `register_layer_adapter` takes the adapter class.

A strict checker rejects an adapter class whose constructor takes an `Image`
against a protocol constructor that takes a `Layer`. The prototype's
`LayerAdapter` has only `close()`, and
`register_layer_adapter(backend, layer_type, factory)` takes a factory typed
`Callable[[LayerT, View], LayerAdapter]` for the layer type it serves. The
registry wraps each factory in a function that checks
`isinstance(layer, layer_type)`, which narrows the layer for the checker with
no cast. `create_layer_adapter(backend, layer, view)` walks the layer type's
MRO, as the target asks, and raises `LookupError` when no type has an adapter.
A class whose constructor has the right signature is itself such a factory, so
the vispy backend registers `VispyImageAdapter` directly.

Recommendation: change the target.

### How the vispy image adapter reaches its scene

The target's adapter is built from a layer and a view only, and a backend has
one surface per view.

A vispy visual must be attached to the scene of the canvas it is drawn on,
which the layer and view do not know. The vispy adapter builds its visual with
no parent and exposes it as `visual`. The surface creates the adapter through
the registry, checks it against a vispy-specific protocol,
`VispyLayerAdapter` (a `LayerAdapter` with a `visual` whose `parent` can be
set), and attaches the visual to its scene. An adapter without a visual is
closed and refused with `TypeError`. Layers are drawn in the order their
adapters were made.

Recommendation: change the target. The adapter protocol, or each backend's
extension of it, should say how an adapter reaches the surface that draws it.

### `RenderSurface` and `RenderBackend` follow rendercanvas and are generic

The target's `RenderSurface` has `input`, `state` and `frame_drawn` signals,
`native: object`, `screenshot(size, wait)` and `close()`, and is to follow
rendercanvas's vocabulary; its `RenderBackend` has `name`, `capabilities` and
`create_surface(view, host: object)`.

The prototype's `RenderSurface[NativeT_co]` uses rendercanvas's names:
`get_physical_size`, `get_logical_size`, `get_pixel_ratio`, `request_draw`
and `add_event_handler(handler, *types)`, plus a `native` property,
`screenshot()` and `close()`. `RenderBackend[NativeT]` has `name` and
`create_surface(view, parent: NativeT | None)`. The native type is a type
parameter, so the core names no GUI toolkit and the front end still gets its
own type back: the example uses `VispyBackend[QWidget]`, and `surface.native`
is a `QWidget` to the checker. There are no `input`, `state` or `frame_drawn`
signals, no `SurfaceState`, `Viewbox` or `Capabilities`, and `screenshot` takes
no size and does not wait. There is no way to remove an event handler.

A rendercanvas canvas would still not satisfy this protocol. Before the code
was written, rendercanvas 3.0.0 had no `screenshot` and no public `native`,
its `add_event_handler` took `(*args, order=0)` with handlers typed
`Callable[[dict], None]`, and it shipped no `py.typed`. A pygfx backend would
therefore wrap the canvas in a small class. This was not checked again;
rendercanvas is not installed in the prototype's environment.

Recommendation: change the target to make the protocols generic in the native
type and to align the member names with rendercanvas, as the prototype does,
and add a way to remove a handler. `frame_drawn` and the capabilities return
when a stage needs them.

### The canvas size is written by `interaction`

The target has the view apply each `SurfaceState` to its canvas model's size.

In the prototype the surface emits a `resize` surface event, and the
dispatcher that `attach` installs writes `view.canvas_size` from it. A surface
that is not attached therefore leaves the view at its default size. The vispy
surface reads `canvas_size` to set its own camera, and `interaction` reads it
to convert surface pixels into world coordinates.

Recommendation: change the target to say which package writes the canvas size
back, or make it part of attaching a surface.

### Two levels of events

The target has a surface emit events in rendercanvas's vocabulary and surface
pixels, and `interaction` turn each into an input event of section 3.5.

The prototype does this. The surface events in `napari_core.render` are typed
dictionaries with rendercanvas's keys and units, `SurfacePointerEvent`,
`SurfaceWheelEvent`, `SurfaceEnterLeaveEvent` and `SurfaceResizeEvent`, whose
union `SurfaceEvent` a `match` on `event_type` narrows. Positions and sizes are
in logical pixels. rendercanvas's `ntouches` and `touches` are left out
because nothing reads them, and enter and leave events carry no position, as
in rendercanvas. The vispy surface translates vispy's mouse events: a wheel
step becomes `dx` and `dy` of 120 per notch, negative when the wheel turns
away from the user, and pointer moves are coalesced, so the latest move is
emitted at the next draw, or before any other pointer or wheel event.

Three things the target expects are missing from the vispy surface. vispy has no
pointer enter or leave events, so the surface emits none. vispy itself drops a
pointer move that arrives within 10 ms of the previous one, so the last
position of a fast movement may not be reported. And the surface draws layers
in the order their adapters were made, so a reordered layer list does not
change the drawing order. The last is a gap in the surface's own code, which
does not reorder its visuals; vispy is not the cause.

Recommendation: change neither for the event types, which the target already
asks for. The target's statement that a backend fills in missing events from
its own state should name enter and leave as known gaps of vispy.

### A surface lives as long as its native widget

The target does not say what keeps a surface alive or when it closes.

Every link from vispy and from psygnal to the vispy surface is weak: vispy
holds an event handler that is a bound method by a weak reference to its
object, and psygnal does the same. A surface that nothing else held was freed,
leaving a window that kept its first picture and responded to nothing. The
surface therefore sets a reference to itself as an attribute of its native
widget, so it lives as long as the widget object does, whether or not the
caller keeps it. `surface.close()` releases it, and so does dropping the
widget. Closing the widget with its own `close()` does not: vispy's Qt backend
does not pass a widget's close event on to the canvas, and a hook of the
surface's own would need Qt in the core, which the dependency rules of
section 2 forbid. A widget that is closed but still
referenced keeps following the model.

The front end therefore has to call `surface.close()` when it closes the
window that hosts the surface. The target's `FrontEnd` protocol in section 3.6
has `show_viewer` and `add_panel`, and says nothing about who closes a surface
or when.

Recommendation: change the target. Section 3.6 should make the front end
responsible for closing each surface it hosts when the window or panel that
holds it closes.

### Display scaling on the development machine

The target does not discuss the pixel ratio beyond following rendercanvas's
vocabulary.

On the development machine, a Windows display set to 150%, Qt reported a
device pixel ratio of 1.0 in some runs and 1.5 in others, with the same code
and no `QT_SCALE_FACTOR` set. Qt also printed that it could not set the
process's DPI awareness. The cause was not investigated. The picture and
dragging were correct at both ratios. The backend's tests were run at a
ratio of 1.5 by setting `QT_SCALE_FACTOR=1.5`: the screenshots are in device
pixels, 300 by 150 for a 200 by 100 surface, while sizes and pointer positions
are in logical pixels, and the tests pass.

Recommendation: change neither; check on other machines before relying on the
pixel ratio a surface reports.

## 3.5 Input

### Input events are built in `interaction`, with some fields constant

The target defines the input event classes in `napari_core.model` and has
`interaction` complete them with world coordinates.

The prototype defines `InputEvent`, `CanvasEvent`, `PointerEvent`,
`ButtonEvent`, `WheelEvent`, `EnterLeaveEvent` and `Modifier` in
`napari_core.model` with the target's fields; `KeyEvent` is left out with key
events. The dispatcher in `napari_core.interaction` builds each event from a
surface event. Several fields are constants in the prototype:

- `viewbox` is always `(0, 0)`, because there is no grid.
- `view_direction` and `up_direction` are always `None`, because the display
  is two-dimensional.
- `inverted` is always `False`, because no surface reports the platform's
  scroll direction.
- an `EnterLeaveEvent` always has no modifiers, and takes the last position the
  surface reported.

`position` holds the world coordinates of the pointer on the two displayed
axes and the current step on every other axis, and `dims_point` holds the
current step as floats. `button` comes from the surface event and is `0` when
no button is involved, never `None`. A modifier name other than `Shift`,
`Control`, `Alt` or `Meta` makes the handler raise `ValueError`.

Recommendation: change neither for the constants, which follow from the
prototype's scope. The target should say what `button` holds when no button
is involved.

### Callbacks go to the top visible layer

The target dispatches to the viewer's handlers first, then to the active
layer's handlers for its mode, then to the camera controller.

The prototype has no viewer handlers, no active layer and no modes. Its
dispatcher gives an event to the callbacks of the top visible layer in the
view's list, then to the camera controller. A press calls each drag callback;
a callback that returns a generator is advanced once and resumed on each move
and on the release, and before each step the dispatcher copies the fields of
the new event into the event the generator received on press, as the target
describes. A callback or generator that raises is logged with
`logging.exception`, naming the callback and the layer, and skipped, so one
broken callback does not stop interaction. Wheel events go to the layer's
wheel callbacks. Move events without a drag, double clicks, and enter and
leave events reach no callback, because the prototype has no lists for them,
and nothing writes a cursor position.

Recommendation: change the target to say that a raising callback is logged and
skipped, and what takes the place of the active layer when no layer is
selected.

### What `handled` does to the camera

The target has the camera controller act only when no handler set `handled`,
pan while `mouse_pan` is true, zoom while `mouse_zoom` is true, and not
receive wheel events with modifiers.

The prototype's camera controller sees every button and wheel event, so that
its drag stays in step with the mouse; `handled` only stops it from moving the
camera. Only the left button drags. A handled press does not start a drag. A
handled move moves the drag's starting point without panning, so the picture
does not jump when the handler stops handling moves. A release of the left
button ends the drag whether handled or not, and a release of another button
does not. A generator that sets `handled` on a later step marks the move or
release event too. Unlike the target, a wheel event with modifiers zooms
like any other.

The wheel zooms by the factor `1.1 ** (-dy / 100)`, with `dy` in
rendercanvas's units, so one notch away from the user zooms in by about 12%,
and the world point under the pointer stays fixed. A step that would leave
the zoom or the centre not finite, or the zoom not above zero, is skipped.

Recommendation: change the target to state these rules and a wheel factor;
whether wheel events with modifiers should reach the camera is for the
target to decide, and the prototype should then follow.

### Attaching twice

The target does not say what attaching a surface twice does.

`attach(view, surface)` returns a function that detaches. Attaching the same
surface and view twice dispatches every event twice. Detaching makes the
handler do nothing but leaves it registered on the surface, because the
surface protocol has no way to remove a handler.

Recommendation: change the target to give the surface a way to remove a
handler (see the `RenderSurface` entry), and change the prototype later to
use it.

### The camera has four fields

The target's camera belongs to a `Scene` and has the fields of napari's
camera.

The prototype's `Camera` is a field of `View` and has four fields: `center`,
`(row, column)` in world coordinates; `zoom`, surface pixels per world unit,
which must be above zero; and `mouse_pan` and `mouse_zoom`, both true by
default, which a layer callback sets to false to keep the camera still. The
other fields of napari's camera, `angles`, `perspective`, `orientation` and
`synced`, belong to three-dimensional display or to several views, which the
prototype leaves out. The surface never writes to the camera; it redraws when
the camera's signals fire.

Recommendation: change neither.

## Known shortcomings left in the code

These are known and left for later, because none of them blocks the prototype
from showing what it was built to show.

- `Transform` does not validate on assignment, so `layer.scale = (1.0,)` is
  accepted for a two-dimensional image, and it does not check that `scale` and
  `translate` have the same length.
- `Dims.nsteps` accepts entries of zero or less.
- After a change of `ndim`, the order in which `nsteps` and `current_step`
  emit was seen to vary between runs.
- `Colormap.name` can be changed on a shared entry of `COLORMAPS`, so one
  layer can rename another's colormap.
- `as_layer_data` rejects NumPy integer scalars in `shape`, and it runs twice
  when an `Image` is built.
- `reset_contrast_limits` copies the finite values of the plane it reads,
  which for in-memory data is the whole array.
- `View(layers=existing_list)` copies the list, and its docstring does not say
  so.
- `Slicer.sync` is not re-entrant: a `sliced` listener that changes the layer
  list during a sync is not handled.
- On a surface of zero size the dispatcher drops every event but `resize`,
  including a release, so a held generator resumes on a later move.
- `NativeT` and `NativeT_co` are not exported from `napari_core.render`, so the
  vispy backend defines its own type variable.
- The camera controller repeats the conversion from surface to world
  coordinates instead of calling `surface_to_world`.
- The comment that records the origin of the one-member protocols does not
  say that `DTypeT_co` has a default that array-api-typing lacks, and gives a
  dask array, not the zarr case above, as the reason `__getitem__` returns
  `object`.
- Some behaviour has no committed test: the error branch of the dask adapter's
  `materialize`, building an input event directly, that the surface never
  writes to the camera, the `Optional[...]` and `Union[...]` spellings of an
  optional component (the same code path as the tested `| None` form), and
  the part of one test that checks a finished generator is not resumed. The
  test helpers build surface events from plain strings, and the tests are not
  type-checked. The static test module uses bare `# type: ignore`, because the
  two checkers name the same error differently.
