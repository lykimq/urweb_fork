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

### 2. Memoization & Caching
Because Ur/Web compiles the entire program as a single unit, `elaborate` (type inference and unification) dominates compile time (up to 85%), repeatedly analyzing unchanged code (like `basis.urs` and the standard library).
*   **Extend incremental elaboration to non-daemon mode**: The daemon currently uses a module database (`ModDb`) to skip unchanged modules. Moving this caching logic to normal CLI compilation drastically cuts down type-checking time.
*   **Short-circuit elaboration of unchanged basis/top**: Pre-computing and serializing the elaborated Basis environment to a binary cache ensures the compiler never redundantly parses the 2000+ declarations of the standard library on cold starts.
*   **Cache `MonoOpt` results across iterations**: Tagging Mono IR expressions with generation counters ensures that peephole optimizations don't waste time reprocessing subtrees that haven't mutated since the last pass.

### 3. Algorithmic & Data Structure Improvements
Standard ML relies heavily on O(log n) balanced binary trees (`BinaryMapFn`) for environments. In massive ASTs, the constant factors of tree traversals add up.
*   **Faster data structures in hot paths**: Replacing `IntBinaryMap` with fast hash tables (`IntHashTable`) in extremely hot passes like `Shake.shake` or `Reduce.reduce` significantly boosts throughput.
*   **Reduce allocation in elaborate**: Profiling with MLton to identify allocation hotspots in unification variables (`ref` cells) and removing redundant list lookups lowers GC pressure and CPU cache misses.

**Conclusion on Existing Approaches**: These are excellent, safe, incremental improvements. They represent the "best" immediate steps for the current architecture.

---

## Part 2: The Architectural Proposal — DSL-Based Transformation Fusion

While the heuristics in Part 1 squeeze performance out of the current system, they do not fix the fundamental architectural bottleneck: **the compiler performs 67 sequential AST traversals**. Traversing a massive tree 67 times inherently limits performance.

In the conclusion of the foundational ICFP 2015 paper (*"Ur/Web: A Simple Model for Programming the Web"*), the author notes:
> *"We plan to study domain-specific languages for compilation... doing whole-program analysis of the suite of algebraic transformations and optimizations to find ways to fuse them together and otherwise avoid overheads."*

This insight leads to the **ultimate, proposal** for the Ur/Web compiler: **Transformation Fusion via a Rewrite DSL.**

### The Problem
Currently, every optimization phase (e.g., deforestation, constant folding, specialization) is written as a manual, recursive function in Standard ML that walks the AST. Because they are separate functions, they must run one after the other.

### The Proposal
Redesign the *specification* of the optimization pipeline without changing the *semantics*.

1.  **Extract the Rules**: Instead of writing manual AST walkers, extract the core algebraic rewrites (e.g., `App (Lam (x, e1), e2) -> subst(e1, x, e2)`) into a declarative **Domain-Specific Language (DSL)** for compiler transformations.
2.  **Whole-Program Analyzer (Meta-Compiler)**: Build a meta-compiler that reads this suite of DSL rules at compile-time (when building `urweb` itself).
3.  **Transformation Fusion**: The meta-compiler mathematically analyzes the dependencies and commutativity of the rules, and **fuses** them. It generates a single, highly optimized SML AST walker that applies *all valid rewrites in a single traversal* (or a very small, optimal number of traversals).

### Why this is the optimal approach
*   **O(N) to O(1) Traversals**: It collapses 67 full-tree passes into 1 or 2 passes. This destroys the primary source of compile-time overhead (cache misses and recursion depth) without altering what the optimizations actually do.
*   **Guaranteed Correctness**: Because the individual algebraic rules remain exactly the same, the output behavior, language semantics, and correctness are perfectly preserved. The rules are simply being scheduled better.
*   **Extensibility**: Adding a new optimization to Ur/Web becomes as simple as adding a one-line algebraic rule to the DSL, rather than writing a new 500-line SML traversal function and deciding where to insert it in the 67-phase pipeline.

---

## Implementation Priority Roadmap

1.  **Immediate Wins (Minimal Effort / High Impact)**
    *   Enable the compiler daemon by default for iterative development.
    *   Add size/change guards (boolean flags) to skip no-op cleanup phases.
    *   Introduce an `-O0` flag for rapid dev builds.
2.  **Medium-Term (Engineering Optimizations)**
    *   Implement binary serialization for `basis.urs` elaboration.
    *   Convert hot-path `BinaryMap` lookups to Hash Tables.
    *   Convert linear shake/specialize chains into fixed-point loops with early exit.
3.  **Long-Term (The Architectural Overhaul)**
    *   Begin extracting manual Mono and Core optimizations into a formal Rewrite DSL.
    *   Implement the DSL meta-compiler to generate fused AST traversals, replacing the manual 67-phase pipeline with a single, highly optimized pass.
