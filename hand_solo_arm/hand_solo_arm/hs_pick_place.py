#!/usr/bin/env python3
from typing import List
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
import rclpy
from rclpy.action import ActionClient
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import MotionPlanRequest, Constraints, JointConstraint
from action_msgs.msg import GoalStatus
from moveit_msgs.msg import MoveItErrorCodes
from std_msgs.msg import Bool

class HSWaypointRunner(LifecycleNode):
    """Minimal: define a waypoint, execute, wait; then define the next one."""

    JOINT_NAMES: List[str] = ['joint_1','joint_2','joint_3','joint_4','joint_5','joint_6']
    PLANNING_GROUP: str = 'tmr_arm'
    ACTION_NAME: str = '/move_action'  # keep identical to your setup

    def __init__(self):
        super().__init__('hs_arm')
        self.client = ActionClient(self, MoveGroup, self.ACTION_NAME)
        self.get_logger().info('Waiting for MoveGroup action server...')
        self.client.wait_for_server()
        self.get_logger().info('MoveGroup action server ready.')
        self.completion_publisher = self.create_publisher(Bool, '/hs_arm/sequence_complete', 10)

        self.pickup_1 = [
            0.785398, 0.174533, 1.91986,
            1.0472, -1.5708, 0.0
        ]

        self.pickup_2 = [
            -0.349066, 0.174533, 1.91986,
            1.0472, -1.5708, 0.0
        ]

        self.carry_pose = [
            0.0, -1.11701, 2.0944,
            0.872665, -1.5708, 0.0
        ]

        self.place_pose = [
            0.0, 0.0, 1.8326,
            1.309, -1.5708, 0.0
        ]

        self.sequence = [
            ('Pickup position 1', self.pickup_1, 3.0),
            ('Pickup position 2', self.pickup_2, 3.0),
            ('Carry position', self.carry_pose, 0.0)
        ]

        self.sequence_index = 0
        self.sequence_running = False
        self.arm_active = False
        self.box_present = False
        self.pending_timer = None
        self.current_goal_handle = None


    def on_configure(self, state):
        self.get_logger().info(
        'Arm configured. Waiting for box detection.')
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state):
        if self.sequence_running:
            self.get_logger().warn(
            'Arm sequence already running.')
            return TransitionCallbackReturn.FAILURE
        
        self.get_logger().info(
        'Box detected! Activating arm.')
        self.arm_active = True
        self.sequence_running = True
        self.sequence_index = 0
        # Schedule movement after activation has completed
        self.schedule_next_move(0.1)
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state):
        if self.sequence_running:
            self.get_logger().warn(
            'Cannot deactivate while arm is moving.')
            return TransitionCallbackReturn.FAILURE
        self.arm_active = False
        self.get_logger().info('Arm deactivated.')
        return TransitionCallbackReturn.SUCCESS

    # --- helpers --------------------------------------------------------------
    def _goal_from_joints(self, joints: List[float]) -> MoveGroup.Goal:
        goal = MoveGroup.Goal()
        req = MotionPlanRequest()
        req.group_name = self.PLANNING_GROUP
        req.num_planning_attempts = 10
        req.allowed_planning_time = 5.0
        req.max_velocity_scaling_factor = 0.5
        req.max_acceleration_scaling_factor = 0.5

        cs = Constraints()
        for name, val in zip(self.JOINT_NAMES, joints):
            jc = JointConstraint()
            jc.joint_name = name
            jc.position = val
            jc.tolerance_above = 0.01
            jc.tolerance_below = 0.01
            jc.weight = 1.0
            cs.joint_constraints.append(jc)

        req.goal_constraints.append(cs)
        goal.request = req
        goal.planning_options.plan_only = False  # plan + execute
        return goal

    def schedule_next_move(self, delay):
        if self.pending_timer is not None:
            self.pending_timer.cancel()
            self.destroy_timer(self.pending_timer)
            self.pending_timer = None

        self.pending_timer = self.create_timer(
            delay,
            self.execute_next_move
        )
    def execute_next_move(self):

        # Stop the timer from repeating
        if self.pending_timer is not None:
            self.pending_timer.cancel()
            self.destroy_timer(self.pending_timer)
            self.pending_timer = None

        if not self.arm_active:
            return

        if self.sequence_index >= len(self.sequence):
            self.finish_sequence()
            return

        name, joints, delay = self.sequence[self.sequence_index]

        if not self.client.server_is_ready():
            self.fail_sequence('MoveGroup server unavailable.')
            return

        self.get_logger().info(f'Executing {name}...')

        goal = self._goal_from_joints(joints)

        future = self.client.send_goal_async(goal)
        future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):

        try:
            handle = future.result()

            if not handle or not handle.accepted:
                self.fail_sequence('MoveIt goal rejected.')
                return

            self.current_goal_handle = handle

            result_future = handle.get_result_async()
            result_future.add_done_callback(self.goal_result_callback)

        except Exception as exc:
            self.fail_sequence(f'Goal error: {exc}')

    def goal_result_callback(self, future):

        try:
            result = future.result()
            self.current_goal_handle = None

            if result.status != GoalStatus.STATUS_SUCCEEDED:
                self.fail_sequence(
                    f'MoveIt action failed: {result.status},'
                    f'MoveIt error: {result.result.error_code.val}'
                )
                return

            if result.result.error_code.val != MoveItErrorCodes.SUCCESS:
                self.fail_sequence(
                    f'MoveIt error: {result.result.error_code.val}'
                )
                return

            name, joints, delay = self.sequence[self.sequence_index]

            self.get_logger().info(f'{name} complete!')

            self.sequence_index += 1
            self.schedule_next_move(delay if delay > 0 else 0.1)

        except Exception as exc:
            self.fail_sequence(f'Result error: {exc}')

        
    def finish_sequence(self):
        self.sequence_running = False
        self.get_logger().info(
            'Pickup sequence complete! Arm is carrying the box.'
        )
        msg = Bool()
        msg.data = True
        self.completion_publisher.publish(msg)

    def fail_sequence(self, message):
        self.sequence_running = False
        self.get_logger().error(
            f'Arm sequence stopped: {message}'
        )



def main(args=None):
    rclpy.init(args=args)
    node = HSWaypointRunner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Interrupted by user.')
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()