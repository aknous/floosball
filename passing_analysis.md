# Passing Play Mechanics Analysis

## Current Implementation Comparison

### Running Plays (Sophisticated Probability Curves)

**Structure:**
- **Two-stage probability system**: Stage 1 (initial contact) + Stage 2 (breakaway potential)
- **Gaussian (bell curve) distribution** for Stage 1 yardage
- **Exponential decay distribution** for Stage 2 yardage

**Key Features:**
```python
# Stage 1: Bell curve based on offense vs defense matchup
mean_stage1 = (stage1Offense - defenseRunCoverageRating) / 5
std_dev_stage1 = calculated based on relative strength and absolute skill
stage1Curve = Gaussian distribution
stage1YardsGained = np.random.choice(stage1Yardages, p=stage1Curve)

# Stage 2: Exponential decay for breakaway yards (if Stage 1 successful)
stage2DecayRate = based on offensive speed vs defensive coverage
stage2Curve = exponential decay
stage2YardsGained = np.random.choice(stage2Yardages, p=stage2Curve)
```

**Advantages:**
- Realistic yardage distribution (most runs 2-5 yards, occasional big gains)
- Smooth scaling based on player skill differentials
- Breakaway potential naturally emerges from Stage 1 success
- No arbitrary threshold buckets

---

### Kicking (Logistic Probability Function)

**Structure:**
- **Single-stage logistic curve** for success probability
- Distance as primary factor with skill modifier

**Key Features:**
```python
baseProbability = 1 / (1 + exp(distanceFactor * (fgDistance - 50)))
probability = baseProbability * (normalizedSkill * skillFactor)
success = roll <= probability
```

**Advantages:**
- Realistic success rate degradation with distance
- Smooth probability curve (no sudden drop-offs)
- Clear skill-based modifiers

---

### Passing Plays (Current: Threshold-Based)

**Structure:**
- **Binary threshold checks** at multiple stages
- **Hard-coded yardage ranges** based on pass type
- **Nested if/else statements** for outcomes

**Current Logic:**
1. **Completion Check**: `accRoll < adjustedQBAccuracy` (with defense modifier)
2. **Drop Check**: `adjustedHands > dropRoll` (defense-influenced)
3. **Yardage Determination**:
   - Short pass: `randint(0,5)` for air yards
   - Medium pass: `randint(5,10)` for air yards
   - Deep pass: `randint(11,20)` for air yards
4. **YAC (Yards After Catch)**:
   - Receiver vs Defense comparison
   - Bucketed outcomes: `if x < 2`, `elif x >= 2 and x < 5`, etc.
   - Hard-coded ranges: `randint(0,3)`, `randint(4,7)`, `randint(7, yardsToEndzone)`

**Issues:**
1. **Uniform distributions** within each range (0-5 yards all equally likely for short passes)
2. **Arbitrary buckets** for YAC determination
3. **No smooth scaling** - difference between 79 accuracy and 80 accuracy is same as 50 vs 51
4. **Hard pass type boundaries** - short pass is ALWAYS 0-5 yards, never 6
5. **Limited variance** - outcomes are very predictable within buckets
6. **YAC logic duplicated** across all three pass types with minimal variation

---

## Assessment: Is Probability Curve Worth Implementing?

### Arguments FOR Implementing Probability Curves

**1. Consistency with Running Plays**
- Running plays have sophisticated curves; passing should match that quality
- Players will notice discrepancy in realism between run/pass outcomes

**2. More Realistic Yardage Distributions**
Currently:
- Short pass: 0-5 yards uniform = unrealistic (most should be 2-4 yards)
- Medium pass: 5-10 yards uniform = unrealistic (should peak around 7-8)
- Deep pass: 11-20 yards uniform = unrealistic (should favor 12-15, rare 18-20)

With curves:
- Short pass: Bell curve centered at 3 yards (skinnier distribution)
- Medium pass: Bell curve centered at 7 yards
- Deep pass: Bell curve centered at 13 yards, with tail for 18-20+ yard bombs

**3. Better Skill Differentiation**
Current: Elite QB (95 accuracy) vs Good QB (85 accuracy) both complete passes at similar rates within their thresholds

With curves: Elite QB's distribution shifts toward higher completion % AND better average yardage

**4. YAC Can Be More Dynamic**
Current YAC is binary (beat defender or not) then bucketed

Potential: YAC as exponential decay based on:
- Receiver speed/agility vs defensive speed
- Open field ahead
- Receiver's play-making ability

**5. Natural Variance**
Curves introduce realistic variance without hard buckets:
- Same players, same situation = different realistic outcomes
- Outlier performances (12-yard "short" pass on perfect read) become possible but rare
- No more "if x < 2" artificial thresholds

**6. Pass Depth Flexibility**
Current: Pass types locked to ranges (short = 0-5, medium = 5-10, deep = 11-20)

Potential: Pass types as probability distributions that can overlap:
- Short pass CAN occasionally be 7 yards (on perfect throw)
- Deep pass CAN be 9 yards (if QB pressured, underthrown)
- More realistic play outcomes

---

### Arguments AGAINST

**1. Complexity**
- Passing already has many factors (QB accuracy, receiver hands, coverage, YAC)
- Adding curves increases computational overhead
- More difficult to tune/balance

**2. Current System Works**
- Passing plays currently generate reasonable stats
- If completion rates and yardage averages are already balanced, why change?
- Risk of breaking existing balance

**3. Development Time**
- Non-trivial implementation effort
- Need to tune multiple distribution parameters
- Extensive testing required

**4. Diminishing Returns**
- Running plays NEEDED curves because distance is continuous variable
- Passing has more discrete stages (completion, YAC) that may not benefit as much
- The biggest realism gains might come from other improvements (route running, coverage logic)

---

## Recommendation: **YES, Worth Implementing**

### Rationale:
1. **Quality gap is noticeable**: Running plays feel more realistic than passing plays in their current state
2. **Passing is core mechanic**: It's ~50% of offensive plays, deserves same care as running
3. **Low-hanging fruit**: Air yardage conversion is straightforward (similar to FG probability)
4. **Scalable approach**: Can implement in stages:
   - Phase 1: Air yardage probability curves (easier)
   - Phase 2: YAC probability curves (moderate)
   - Phase 3: Route-running and coverage depth modeling (advanced)

### Suggested Implementation Approach:

**Phase 1: Air Yardage Curves (High Value, Moderate Effort)**

```python
# For each pass type, create Gaussian distribution for air yards
passTypeMean = {1: 3, 2: 7, 3: 14}  # short, medium, deep
passTypeStdDev = {1: 1.5, 2: 2, 3: 3}  # short has tighter distribution

# Adjust mean based on QB accuracy, pressure, coverage
adjustedMean = passTypeMean[passType] * (qbAccuracy / 80)  # Example

# Sample from distribution
airYards = sample_from_gaussian(adjustedMean, passTypeStdDev[passType])
```

**Benefits:**
- Eliminates hard yardage buckets
- Elite QBs get better average air yardage on same route
- Pressure affects not just completion but also throw quality
- Natural variation (same play = different yardage outcomes)

**Phase 2: YAC Probability Modeling (High Value, Higher Effort)**

```python
# YAC as exponential decay based on:
# - Receiver speed/agility differential vs defense
# - Open field space
# - Play-making ability

yacPotential = calculate_max_yac(yardsToEndzone, fieldPosition)
yacRate = calculate_decay_rate(receiverSkill, defenseCoverage)
yacCurve = exponential_decay(yacRate, yacPotential)
yac = np.random.choice(yacRange, p=yacCurve)
```

**Benefits:**
- Elite receivers consistently get more YAC than average receivers
- Defense quality properly impacts YAC (not just binary comparison)
- Occasional big plays emerge naturally from curves
- Can model "juke moves" and broken tackles through distribution tails

---

## Conclusion

**Verdict: Implement probability curves for passing plays**

The current threshold-based system with uniform distributions is significantly less sophisticated than the running play mechanics. Passing is a core game mechanic that deserves the same level of statistical modeling.

**Priority:**
1. **High**: Air yardage Gaussian distributions (quick win, high impact)
2. **Medium**: YAC exponential decay modeling (more complex, still valuable)
3. **Low**: Advanced route/coverage depth modeling (diminishing returns)

**Expected Outcomes:**
- More realistic passing statistics
- Better skill differentiation between players
- Consistent quality across run/pass mechanics
- More exciting variance in pass outcomes
- Foundation for future improvements (route trees, coverage shells, etc.)
