from launch import LaunchDescription
from launch.actions import EmitEvent, RegisterEventHandler
from launch.events import matches_action
from launch_ros.actions import LifecycleNode, Node
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution
from lifecycle_msgs.msg import Transition

def generate_launch_description():
    pkg_share   = FindPackageShare('hand_solo_virtual_nav')
    slam_params = PathJoinSubstitution([pkg_share, 'config', 'pa_slam_params.yaml'])
    rviz_cfg    = PathJoinSubstitution([pkg_share, 'rviz',   'pa_rviz_mapping.rviz'])

    # slam_toolbox (Jazzy, >= 2.8) is a lifecycle node: it must be configured
    # and activated, otherwise it never loads params or publishes the map.
    slam_node = LifecycleNode(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        namespace='',
        output='screen',
        parameters=[slam_params, {'use_sim_time': False, 'use_lifecycle_manager': False}]
    )

    configure_slam = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(slam_node),
            transition_id=Transition.TRANSITION_CONFIGURE
        )
    )

    activate_slam = RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=slam_node,
            start_state='configuring',
            goal_state='inactive',
            entities=[
                EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(slam_node),
                    transition_id=Transition.TRANSITION_ACTIVATE
                ))
            ]
        )
    )

    return LaunchDescription([
        slam_node,
        configure_slam,
        activate_slam,
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', rviz_cfg],
            parameters=[{'use_sim_time': False}]
        ),

    ])
