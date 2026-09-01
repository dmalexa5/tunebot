# Example report (use this as a template)

<!-- This is an example tune-chatter report -->

### Final gains:

<!-- Update these values with final gains -->
- `POS_KP = value`
- `POS_KI = value`
- `VEL_KI = value`
- `VEL_KP = value`

### Sweep comparison 

<!-- Update this table using measured values from the test -->
┌─────────┬──────────────────────┬───────────────────┬───────────────────────────────┐
│  freq   │ baseline jit / band2 │ tuned jit / band2 │ tracking err_rms (base→tuned) │
├─────────┼──────────────────────┼───────────────────┼───────────────────────────────┤
│ 0.1 Hz  │ 740mA / 0.76A        │ 68mA / 0.016A     │ 0.447 → 0.288 mrad            │
├─────────┼──────────────────────┼───────────────────┼───────────────────────────────┤
│ 0.25 Hz │ 543mA / 0.95A        │ 76mA / 0.061A     │ 1.512 → 1.489 mrad            │
├─────────┼──────────────────────┼───────────────────┼───────────────────────────────┤
│ 0.5 Hz  │ 523mA / 0.51A        │ 75mA / 0.051A     │ 5.055 → 5.047 mrad            │
├─────────┼──────────────────────┼───────────────────┼───────────────────────────────┤
│ 0.75 Hz │ 507mA / 1.35A        │ 76mA / 0.037A     │ 9.384 → 9.360 mrad            │
├─────────┼──────────────────────┼───────────────────┼───────────────────────────────┤
│ 1.0 Hz  │ 671mA / 1.21A        │ 93mA / 0.062A     │ 14.179 → 13.770 mrad          │
└─────────┴──────────────────────┴───────────────────┴───────────────────────────────┘

### Notes

<!-- Write a concise summary of the test and place it here -->

### Captures

<!-- List the captures for baseline gains -->
- `traces/j1-chatter-reduction/psine.0000.txf`

<!-- List the captures for final gains -->
- `traces/j1-chatter-reduction/psine.0040.txf`