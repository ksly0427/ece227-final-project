# ECE 227 Final Project

## Group Members
- Kenny Ly (A16132197)
- Nathan Bui (A15847396)

## Base Usage
Run this command to run the base SEIR model using US parameters
```
python run_simulation.py -v --best_params_dir best_params/latest --country US
```

## Modified Usage
Run these command to run the modified SEIR model described in the project

### 50% Mask Usage, 10% Mask Effectiveness
```
python run_simulation.py -v --best_params_dir best_params/latest --country US --mask_perc 0.5 --mask_effectiveness 0.1 --simulation_end_date 2020-11-01
```

### 50% Mask Usage, 25% Mask Effectiveness
```
python run_simulation.py -v --best_params_dir best_params/latest --country US --mask_perc 0.5 --mask_effectiveness 0.25 --simulation_end_date 2020-11-01
```

### 50% Mask Usage, 50% Mask Effectiveness
```
python run_simulation.py -v --best_params_dir best_params/latest --country US --mask_perc 0.5 --mask_effectiveness 0.5 --simulation_end_date 2020-11-01
```

### 50% Mask Usage, 75% Mask Effectiveness
```
python run_simulation.py -v --best_params_dir best_params/latest --country US --mask_perc 0.5 --mask_effectiveness 0.75 --simulation_end_date 2020-11-01
```

