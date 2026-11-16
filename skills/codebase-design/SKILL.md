---
name: codebase-design
description: Use when shaping a module, an interface or a boundary before writing it, or when existing code keeps fighting the change being made.
---

# Design

Decide the shape before filling it in.
A module here is anything with an interface and an implementation: a function, a class, a package.
Its interface is everything a caller must know to use it correctly: signatures, but also ordering, invariants, error modes and required setup.

## 1. Ground it

Read every piece of code the new shape will touch and write two or three sentences on how each works today.
Naming a file is not grounding.
Use the project's existing words for things; when a term is vague or used two ways, settle it before it becomes a type name.

## 2. Write the caller first

Write the code a caller would want to write, before any signature.
Then derive the types and signatures from that usage, with unimplemented bodies.
Small change: one file of types and signatures.
Larger work: a module list, each with its interface and what it hides.

## 3. Design it twice

Produce at least two designs that differ in shape, not in detail, even when the first looks good enough.
Useful pressures to design under: fewest entry points; the common caller's case made trivial; maximum flexibility.
Compare them on:

- **Depth**: how much behavior sits behind how little interface. Prefer the small interface with a lot behind it.
- **Locality**: whether a future change, bug or rule lives in one place.
- **Where the boundary sits**: what varies across it today. One implementation behind an interface is a guess; two is a real boundary.

Recommend one and say why; propose a hybrid only when the parts fit.

## 4. Screen for these before choosing

- **Shallow module**: callers coordinate several calls for one operation, or options expose internal stages.
- **Leaked decision**: a representation, wire format or policy appears in more than one module, so changing it means coordinated edits.
- **Split by time**: modules named load, validate, transform, save that all repeat one representation and its rules. Group by the knowledge owned instead.
- **Pass-through**: a method that forwards the same arguments to the same shape. Imagine deleting the module: if nothing gets harder, delete it.
- **Two owners**: more than one module writes the same state or keeps its own copy.
- **Two ways to do one thing**: every way keeps gaining callers. Keep one and move the callers.
- **Reachable internals**: if an outside import compiles, it becomes interface.
- **Hand-synced lists**: the same items listed in two places. Derive one from the other or fail the build when they disagree.

Assume the next editor sees only the files they opened and copies the nearest example.
Prefer the design where a change that looks right from one file is right for the whole codebase.

## 5. Make it testable through the interface

- Accept dependencies instead of creating them.
- Return results instead of mutating arguments.
- Tests cross the same boundary callers do; wanting to test past the interface means the module is the wrong shape.

## 6. Implement against the sketch, and scrap it when it fights

The sketch is the contract.
When a function needs something the sketch did not anticipate, decide which was wrong: the sketch, the requirement, or the implementation reaching too far.

Throw the sketch away when the friction forms a pattern:

- the same workaround in unrelated places;
- several edge cases each needing a special branch;
- types that need casts or always-set optional fields to compile;
- callers needing the module's internal rules to use it.

A few hard cases do not condemn a design; some problems are complicated.
When you do scrap, redesign as if the new constraints had been known from the start, make the new sketch smaller than the old one, and return to step 3.

## Output

The caller usage, the chosen signatures, the alternative that lost and why, and what the design deliberately does not handle.
