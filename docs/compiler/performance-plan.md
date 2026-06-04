# Ur/Web Compiler Performance Improvement Plan

**Constraint**: No changes to output behavior, language semantics, or IR design correctness.
**Goal**: Reduce wall-clock time of `urweb -timing app` without altering what the generated C / JS does. 

This document serves as a deep analytical evaluation of current engineering heuristics for the Ur/Web compiler and presents a fundamental, highly optimized architectural proposal inspired by Ur/Web research literature.

---

## Part 1: Deep Analysis of Existing Optimization Approaches

The Ur/Web compiler (`compiler.sml`) currently runs roughly 67 distinct optimization and checking passes over its Intermediate Representation (IR). The existing approaches focus on practical engineering optimizations that avoid unnecessary work. These are **correct, highly implementable, and safe**, as they target the *mechanics* of the compiler (caching, loop unrolling, memory allocation) rather than altering the semantic rewrites.

We can categorize the existing operational optimizations into three main areas:

### 1. Redundancy Elimination
The compiler frequently performs passes over the AST where no rewrites actually occur (e.g., executing a cleanup pass when the previous pass made no changes).
*   **Skip no-op phases via size/change guards**: By introducing a simple `changed` boolean or comparing AST size before and after, we can entirely skip subsequent cleanup phases (like `shake` or `untangle`).
*   **Merge repeated shake/specialize/unpoly loops**: Core passes run in a hardcoded linear chain with repeated iterations (e.g., `especialize1' -> shake1' -> ...`). Wrapping these in a fixed-point loop that exits early upon convergence saves multiple full tree traversals.
*   **Disable optional/unused phases conditionally**: Introducing flags (like `-O0` for dev builds) or guarding unused passes (like `endpoints` or `css` extraction) prevents the compiler from walking the AST for features the user hasn't requested. [Do not implement this feature]
*   **How to verify and check**: 
    1. **Correctness Check (Native Test Suite)**: We added `tests/opt_test.ur` and `tests/opt_test.py` to the codebase's test suite to verify that the optimized compiler compiles polymorphic/monomorphic code correctly and produces valid executable outputs.
       Run the test from the `tests` directory:
       ```bash
       cd tests && ./driver.sh opt_test
       ```
    2. **Profiling (Timing Checks)**: Compiling with `-timing` prints the timing list of executed phases. Cleanup phases skipped by size guards will be completely omitted from this list, and loops will terminate early showing fewer iterations.
       ```bash
       urweb -timing <project_file>
       ```

### 2. Algorithmic & Data Structure Improvements
Standard ML relies heavily on O(log n) balanced binary trees (`BinaryMapFn`) for environments. In massive ASTs, the constant factors of tree traversals add up.
*   **Faster data structures in hot paths**: Replacing `IntBinaryMap` with fast hash tables (`IntHashTable`) in extremely hot passes like `Shake.shake` or `Reduce.reduce` significantly boosts throughput.
*   **Reduce allocation in elaborate**: Profiling with MLton to identify allocation hotspots in unification variables (`ref` cells) and removing redundant list lookups lowers GC pressure and CPU cache misses.
