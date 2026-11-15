# Group 6 - Industrial Robots and Systems 2026
Repository which contains the work of Group 6 made for Industrial Robots and Systems, Semester 2 2026

## Build Instructions:

To build and launch the grand challenge solution, the following steps should be taken. 

- In the source folder (src), clone the main branch.

``` bash
git clone -b main https://github.com/roccotheo10-lab/IRS_2026_group_6.git
```

- Change directory into the irs_ws directory in the command line interface and run the following command to build all three packages and source the workspace at once

```bash
colcon build --symlink-install && source install/setup.bash
```

- Once complete, use the ros2 launch command below to use the launch file and begin the automated operations

```bash
ros2 launch hand_solo_virtual_nav challenge_launch.py
```
