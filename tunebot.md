# Tunebot

Utilities and instructions for an agent to tune a joint control loop.

## Goal

Optimize <behavior> while maintaining <constraints> 

## Utilities

```
_tools
├── env.sh# set up environment
├── final.sh# test final gains
├── guard.sh# guard against initial state
├── line.py # oneline summary of a capture
├── pinter.sh # interleaved pos-sine comp, guards against wrap boundary 
├── pstep.py# pos step metrics
├── pstep.sh# 
├── psweep.sh
├── setgains.sh
├── shape.py
├── stats.py
├── step.py
├── txf.py
├── vinter.sh
├── vstep.sh
└── vsweep.sh
```

## Instructions

