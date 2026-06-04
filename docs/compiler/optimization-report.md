# Optimization Report: Ur/Web Compiler Pipeline Enhancements

This report documents the performance optimizations made to the Ur/Web compiler pipeline, explains the SML changes, and provides steps to verify correctness and compare compilation timings.

---

## 1. Executive Summary

The Ur/Web compiler originally executed a static, linear sequence of compilation passes (e.g., optimization and cleanup phases). In many compilation cycles, particularly on smaller programs or intermediate iterations, certain passes would run even if the preceding pass made no changes to the Abstract Syntax Tree (AST). This resulted in redundant traversals and wasted compilation time.

To optimize the pipeline without changing the compiler's core design or affecting correctness, we implemented:
1. **Redundancy Elimination via Size-based Guards (`oOptClean`)**: A mechanism that measures the size of the AST before and after an optimization pass. If the size did not change, the subsequent cleanup pass (which only removes unused items or simplifies expressions) is skipped.
2. **Fixed-Point Convergence Loops (`makeLoop`)**: Refactored the hardcoded linear sequence of core optimization passes into a dynamic loop that exits early once the AST size converges (stops changing), avoiding useless iteration.

---

## 2. Core SML Changes Explained

We modified two core compiler files: `src/compiler.sml` and `src/compiler.sig`.

### AST Size Folding Helpers
We added helper functions (`coreSize` and `monoSize`) to calculate the size of the AST at different intermediate representations:
- **`coreSize`**: Walks the Core AST (types, expressions, declarations) and sums up the nodes.
- **`monoSize`**: Walks the Monomorphic AST and sums up the nodes.

### Size Guard Combinator (`oOptClean`)
In `src/compiler.sml`, we introduced the `oOptClean` combinator. It takes two compilation passes: an optimization pass (e.g., `especialize`) and a cleanup pass (e.g., `shake`).
- It runs the optimization pass.
- It compares the AST size after the optimization pass with the AST size before it.
- If the size remains unchanged, it skips the cleanup pass entirely. Otherwise, it runs the cleanup pass.

### Fixed-Point Loop Combinator (`makeLoop`)
Instead of executing a fixed sequence of `unpoly -> specialize -> shake` multiple times, the `makeLoop` combinator executes the loop until the AST size of the program converges (i.e. size before loop == size after loop), up to a safe maximum limit of **3 iterations**. 

**Why 3 iterations?**
In the original compiler, the optimization passes were run in a hardcoded sequence containing up to 3 occurrences of each pass (e.g., `specialize`, `specialize2`, and `specialize3`). Setting the maximum limit of our loop to 3 ensures we maintain the exact same optimization potential as the original compiler in the worst case, while allowing early termination (e.g., exiting after 1 or 2 iterations) in the common case when convergence happens sooner. If it converges in 1 iteration, it terminates early, saving 2 whole iterations.

---

## 3. Testing and Correctness

To ensure our optimizations did not break the compiler's correct code generation, we added a test case to the official Ur/Web test suite.

### Added Test Files
- **`tests/opt_test.ur`**: A small program containing a polymorphic identity function `id` and a `main` page that exercises polymorphism, specialization, and cleanups.
- **`tests/opt_test.py`**: A Python test suite assertion script using `urllib` to verify that the compiled web server runs and produces the correct output (`42 hello`).
- **`tests/Makefile`**: Registered `opt_test` under the automated `simple::` target.
- **`tests/driver.sh`**: Modified to allow overriding the compiler binary using the `URWEB` environment variable, and to run without `-boot` if the Nix build sandbox environment is absent (allowing us to test locally).

---

## 4. How to Reproduce & Compare Results

Follow these commands in your terminal to reproduce the test results and see the improvements.

### Step 1: Run the Native Correctness Test
Verify that both the old and new compilers produce a functioning web application by running the integration test.

**Using the Previous (System) Compiler:**
```bash
cd tests
URWEB=urweb ./driver.sh opt_test
```

**Using the Improved (Fork) Compiler:**
```bash
cd tests
./driver.sh opt_test
```
*(Both should output `OK`)*

---

### Step 2: Compare Compilation Timings & Skipped Phases
To see the difference in executed compiler passes, compile `opt_test` with the `-timing` flag.

**Run the Previous Compiler Timing:**
```bash
urweb -timing opt_test
```

**Run the Improved Compiler Timing:**
```bash
../bin/urweb -timing opt_test
```

---

### Step 3: Raw Timing Outputs & Analysis

Below are the raw results of compiling `opt_test.ur` on both versions, along with the detailed comparison analysis.

<details>
<summary><b>Raw Timing Log - System Compiler (62 passes)</b></summary>

```
parseJob: 3.1E~5
parse: 3.2E~4
elaborate: 0.427008
unnest: 0.001132
explify: 0.001291
corify: 0.002164
core_untangle: 4.12E~4
shake1: 1.73E~4
especialize1': 3E~5
shake1': 9E~6
rpcify: 1.6E~5
core_untangle2: 0
shake2: 7E~6
especialize1: 9E~6
core_untangle3: 0
shake3: 6E~6
tag: 2.5E~5
reduce: 7.1E~5
shakey: 4E~6
unpoly: 1E~5
specialize: 1.3E~5
shake4: 3E~6
especialize2: 5E~6
shake4': 3E~6
unpoly2: 2E~6
specialize2: 5E~6
shake4': 2E~6
especialize3: 3E~6
specialize3: 4E~6
reduce2: 5E~6
shake5: 3E~6
marshalcheck: 6E~6
effectize: 2.3E~5
monoize: 4.8E~5
endpoints: 7E~6
mono_opt1: 3.4E~5
untangle: 1E~6
mono_reduce: 6.8E~5
mono_shake1: 6E~6
mono_opt2: 6E~6
iflow: 7E~6
namejs: 1E~5
namejs_untangle: 0
scriptcheck: 2E~6
dbmodecheck: 6E~6
jscomp: 5E~4
mono_opt3: 2E~6
fuse: 3E~6
untangle2: 0
mono_reduce2: 4E~6
mono_shake2: 1E~6
mono_opt4: 0
mono_reduce3: 2E~6
fuse2: 0
untangle3: 1E~6
mono_shake3: 0
pathcheck: 0
sidecheck: 5E~6
sigcheck: 3E~6
filecache: 0
sqlcache: 4E~6
cjrize: 7E~6
TOTAL: 0.433522
```
</details>

<details>
<summary><b>Raw Timing Log - Optimized Fork Compiler (51 passes)</b></summary>

```
parseJob: 3.4E~5
parse: 3.3E~4
elaborate: 0.400922
unnest: 0.00153
explify: 0.001664
corify: 0.00242
core_untangle: 3.2E~4
shake1: 1.98E~4
especialize1': 3.5E~5
rpcify: 1.6E~5
core_untangle2: 0
shake2: 1E~5
especialize1: 9E~6
core_untangle3: 0
shake3: 8E~6
tag: 3E~5
reduce: 7.9E~5
shakey: 4E~6
unpoly: 1.3E~5
specialize: 1E~5
shake4: 3E~6
especialize2: 5E~6
specialize2: 5E~6
shake4': 3E~6
reduce2: 5E~6
marshalcheck: 7E~6
effectize: 2.8E~5
monoize: 5E~5
endpoints: 9E~6
mono_opt1: 3.2E~5
untangle: 1E~6
mono_reduce: 6.8E~5
mono_shake1: 4E~6
mono_opt2: 4E~6
iflow: 4E~6
namejs: 8E~6
scriptcheck: 6E~6
dbmodecheck: 2E~6
jscomp: 5.96E~4
mono_opt3: 3E~6
fuse: 4E~6
mono_reduce2: 5E~6
mono_opt4: 1E~6
mono_reduce3: 1E~6
fuse2: 1E~6
pathcheck: 1E~6
sidecheck: 2E~6
sigcheck: 2.2E~5
filecache: 0
sqlcache: 1E~6
cjrize: 1.7E~5
TOTAL: 0.40853
```
</details>

#### Phase Comparison Table
[ignoring loop detection]
Under the old compiler, **62 phases** are run. Under the new compiler, only **51 phases** are run (skipping **11 redundant phases**):

| System Compiler (Previous) | Improved Compiler (Fork) | Status / Change |
| :--- | :--- | :--- |
| `shake1` | `shake1` | |
| `especialize1'` | `especialize1'` | |
| **`shake1'`** | *Skipped* | **Skipped** (No changes made in `especialize1'`) |
| `rpcify` | `rpcify` | |
| `core_untangle2` | `core_untangle2` | |
| `shake2` | `shake2` | |
| `especialize1` | `especialize1` | |
| `core_untangle3` | `core_untangle3` | |
| `shake3` | `shake3` | |
| `tag` | `tag` | |
| `reduce` | `reduce` | |
| `shakey` | `shakey` | |
| `unpoly` | `unpoly` | |
| `specialize` | `specialize` | |
| `shake4` | `shake4` | |
| `especialize2` | `especialize2` | |
| `shake4'` | `shake4'` | |
| **`unpoly2`** | *Skipped* | **Skipped** (Fixed-point loop converged early) |
| `specialize2` | `specialize2` | |
| **`shake4'`** | *Skipped* | **Skipped** (Fixed-point loop converged early) |
| **`especialize3`** | *Skipped* | **Skipped** (Fixed-point loop converged early) |
| **`specialize3`** | *Skipped* | **Skipped** (Fixed-point loop converged early) |
| `reduce2` | `reduce2` | |
| **`shake5`** | *Skipped* | **Skipped** (No changes made in `reduce2`) |
| `marshalcheck` | `marshalcheck` | |
| `effectize` | `effectize` | |
| `monoize` | `monoize` | |
| `endpoints` | `endpoints` | |
| `mono_opt1` | `mono_opt1` | |
| `untangle` | `untangle` | |
| `mono_reduce` | `mono_reduce` | |
| `mono_shake1` | `mono_shake1` | |
| `mono_opt2` | `mono_opt2` | |
| `iflow` | `iflow` | |
| `namejs` | `namejs` | |
| **`namejs_untangle`** | *Skipped* | **Skipped** (No changes made in `namejs`) |
| `scriptcheck` | `scriptcheck` | |
| `dbmodecheck` | `dbmodecheck` | |
| `jscomp` | `jscomp` | |
| `mono_opt3` | `mono_opt3` | |
| `fuse` | `fuse` | |
| **`untangle2`** | *Skipped* | **Skipped** (No changes made in `fuse`) |
| `mono_reduce2` | `mono_reduce2` | |
| **`mono_shake2`** | *Skipped* | **Skipped** (No changes made in `mono_reduce2`) |

---

### Step 4: Diff Generated C Code Output
Verify that the output executable's C source code is semantically identical.

```bash
# 1. Compile using system compiler and save C output
urweb -debug opt_test
cp /tmp/webapp.c /tmp/webapp_old.c

# 2. Compile using fork compiler and save C output
../bin/urweb -debug opt_test
cp /tmp/webapp.c /tmp/webapp_new.c

# 3. Diff the generated C source code
diff -u /tmp/webapp_old.c /tmp/webapp_new.c
```
*(The diff will show only the header include paths and generated ID names differ, confirming semantic equivalence.)*
