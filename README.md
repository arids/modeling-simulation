
### Distributed Airport Simulation

- Single Thread Simulator
- YAWNS Simulator
- Null Message Simulator (in progress)

The airport_conf.py contains the parameters of the model

### Running instructions

#### Single Thread
```
python main_singlethread.py
```

#### YAWNS simulator
```
 mpiexec -n 3 python main_yawns.py

```

Output folder is created in the current working 
directory. An output file is created per LP