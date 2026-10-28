from launch import LaunchDescription
from launch_ros.actions import Node, LifecycleNode
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.actions import EmitEvent, RegisterEventHandler
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from lifecycle_msgs.msg import Transition
from launch.events import matches_action
from launch.event_handlers import OnProcessStart

def generate_launch_description():
    # Package paths
    nav_pkg_share = FindPackageShare('hand_solo_virtual_nav')
    arm_pkg_share = FindPackageShare('hand_solo_arm')
    status_pkg_share = FindPackageShare('pa_warehouse_status')

    # File paths
    rviz_cfg = PathJoinSubstitution([nav_pkg_share, 'rviz', 'pa_rviz_nav2.rviz'])
    map_yaml = PathJoinSubstitution([nav_pkg_share, 'map', 'pa_warehouse_map_01.yaml'])
    nav2_params = PathJoinSubstitution([nav_pkg_share, 'config', 'pa_nav2_params.yaml'])

    # Launch arguments (optional - for flexibility)
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')

    # Declare launch arguments
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'   
    )

    # Map Server - Lifecycle Node
    map_server = LifecycleNode(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        namespace='',
        output='screen',
        parameters=[
            nav2_params,
            {'yaml_filename': map_yaml,
             'use_sim_time': use_sim_time}
        ]
    )

    # AMCL - Lifecycle Node
    amcl = LifecycleNode(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        namespace='',
        output='screen',
        parameters=[
            nav2_params,
            {'use_sim_time': use_sim_time}
        ]
    )

    # Controller Server - Lifecycle Node
    controller_server = LifecycleNode(
        package='nav2_controller',
        executable='controller_server',
        name='controller_server',
        namespace='',
        output='screen',
        parameters=[
            nav2_params,
            {'use_sim_time': use_sim_time}
        ],
        remappings=[
            ('cmd_vel', 'cmd_vel_nav')   # raw controller output goes to the velocity smoother
        ]
    )

    # Planner Server - Lifecycle Node
    planner_server = LifecycleNode(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        namespace='',
        output='screen',
        parameters=[
            nav2_params,
            {'use_sim_time': use_sim_time}
        ]
    )

    # Behavior Server - Lifecycle Node
    behavior_server = LifecycleNode(
        package='nav2_behaviors',
        executable='behavior_server',
        name='behavior_server',
        namespace='',
        output='screen',
        parameters=[
            nav2_params,
            {'use_sim_time': use_sim_time}
        ]
    )

    # BT Navigator - Lifecycle Node
    bt_navigator = LifecycleNode(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        namespace='',
        output='screen',
        parameters=[
            nav2_params,
            {'use_sim_time': use_sim_time}
        ]
    )

    # Waypoint Follower - Lifecycle Node
    waypoint_follower = LifecycleNode(
        package='nav2_waypoint_follower',
        executable='waypoint_follower',
        name='waypoint_follower',
        namespace='',
        output='screen',
        parameters=[
            nav2_params,
            {'use_sim_time': use_sim_time}
        ]
    )

    # Velocity Smoother - Lifecycle Node
    velocity_smoother = LifecycleNode(
        package='nav2_velocity_smoother',
        executable='velocity_smoother',
        name='velocity_smoother',
        namespace='',
        output='screen',
        parameters=[
            nav2_params,
            {'use_sim_time': use_sim_time}
        ],
        remappings=[
            ('cmd_vel', 'cmd_vel_nav'),       # input: from the controller
            ('cmd_vel_smoothed', 'cmd_vel')   # output: to the robot
        ]
    )

    # Lifecycle Manager for Localization
    lifecycle_manager_localization = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_localization',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'autostart': True},
            {'node_names': ['map_server', 'amcl']}
        ]
    )

    # Lifecycle Manager for Navigation
    lifecycle_manager_navigation = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'autostart': True},
            {'node_names': [
                'controller_server',
                'planner_server',
                'behavior_server',
                'bt_navigator',
                'waypoint_follower',
                'velocity_smoother'
            ]}
        ]
    )

    # RViz2
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_cfg],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

### ADDED BY US ###

    # Pineapple gossip bot
    gossip = Node(
        package="pa_warehouse_status",
        executable='pineapple_gossip_bot',
        name='gossip_bot',
        namespace='',
        output='screen',
    )

    # Pineapple listener
    listener = Node(
        package="pa_warehouse_status",
        executable='plc_hmi_listener',
        name='plc_listener',
        namespace='',
        output='screen',
    )

    # Arm node
    armnode = LifecycleNode(
        package='hand_solo_arm',
        executable='hs_pick_place',
        name='hs_arm',
        namespace='',
        output='screen',
        parameters=[ 
            {'use_sim_time': use_sim_time} 
        ] 
    )
    configure_arm = RegisterEventHandler(
    OnProcessStart(
        target_action=armnode,
        on_start=[
            EmitEvent(
                event=ChangeState(
                    lifecycle_node_matcher=matches_action(armnode),
                    transition_id=Transition.TRANSITION_CONFIGURE
                )
            )
        ]
    )
)


    # Hand solo waypoint follower node 
    #hs_waypoint_follower = LifecycleNode( 
        #package='hand_solo_virtual_nav', 
        #executable='hs_waypoint_follower', 
        #name='hs_waypoint_follower_nav2pose', 
        #namespace='',
        #output='screen', 
        #parameters=[ 
        #    {'use_sim_time': use_sim_time} 
        #    ] 
        #) 
    
    #configure_hs_waypoint_follower = EmitEvent(
        #event=ChangeState(
            #lifecycle_node_matcher=matches_action(hs_waypoint_follower),
            #transition_id=Transition.TRANSITION_CONFIGURE
        #)
    #)

    
    # start position node
    start_we_want = Node(
        package='hand_solo_virtual_nav',
        executable='start_we_want',
        name='start_we_want',
        namespace='',
        output='screen',
        parameters=[ 
            {'use_sim_time': use_sim_time} 
            ] 
    )

    # Detect box -> move arm
    box_coordinator = Node(
    package='hand_solo_virtual_nav',
    executable='box_coordinator',
    name='box_coordinator',
    namespace='',
    output='screen'
)


    return LaunchDescription([
        # Launch arguments
        declare_use_sim_time,

        # Localization Stack
        map_server,
        amcl,
        lifecycle_manager_localization,

        # Navigation Stack
        controller_server,
        planner_server,
        behavior_server,
        bt_navigator,
        waypoint_follower,
        velocity_smoother,
        lifecycle_manager_navigation,

        # Hand solo waypoint follower node 
        #hs_waypoint_follower, 

        # Visualization
        rviz,

        #Pineapple gossip and listener
        gossip,
        listener,
        #arm
        armnode,
        configure_arm,
        box_coordinator,
        #config waypoint follower
        #configure_hs_waypoint_follower,
    ])
