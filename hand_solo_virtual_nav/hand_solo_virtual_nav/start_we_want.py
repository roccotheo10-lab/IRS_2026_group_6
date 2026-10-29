#!/usr/bin/env python3
import math
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
import rclpy
from rclpy.action import ActionClient
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import Bool

class HSWaypointNavigator(LifecycleNode):
    def __init__(self):
        super().__init__('hs_navigation')
        self.client = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.completion_publisher = self.create_publisher(Bool, '/hs_navigation/sequence_complete', 10)

        self.navigation_running = False
        self.navigation_active = False
        self.pending_timer = None
        self.current_goal_handle = None
        self.dropoff_task = False # <-- Added for the iteration. True when navigating to drop-off point

    def on_configure(self, state):
        self.get_logger().info(
            'Navigation configured. Waiting for activation.')
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state):
        if self.navigation_running:
            self.get_logger().warn(
            'Navigation already running.')
            return TransitionCallbackReturn.FAILURE
        
        self.get_logger().info(
        'Navigation activated and now under way.')
        self.navigation_running = True
        self.navigation_active = True
        # Schedule movement after activation has completed
        self.schedule_navigation(0.1)
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state):
        if self.navigation_running:
            self.get_logger().warn(
            'Cannot deactivate while navigation is running.')
            return TransitionCallbackReturn.FAILURE
        self.navigation_active = False
        self.get_logger().info('Navigation ended.')
        return TransitionCallbackReturn.SUCCESS


    # --- Helper function to build a PoseStamped ---
    def make_pose(self, x: float, y: float, yaw: float) -> PoseStamped:
        """
        Create a PoseStamped (position + orientation) in the 'map' frame.
        - x, y are coordinates in meters
        - yaw is robot orientation (heading) in radians
        """
        ps = PoseStamped()
        ps.header.frame_id = 'map'  # always use 'map' for navigation goals
        ps.pose.position.x = x
        ps.pose.position.y = y

        # Convert yaw (in radians) into quaternion (needed by ROS2)
        half = yaw * 0.5
        ps.pose.orientation.z = math.sin(half)
        ps.pose.orientation.w = math.cos(half)
        return ps
    
    def schedule_navigation(self, delay):
        if self.pending_timer is not None:
            self.pending_timer.cancel()
            self.destroy_timer(self.pending_timer)
            self.pending_timer = None

        self.pending_timer = self.create_timer(
            delay,
            self.execute_navigation
        )

    def execute_navigation(self):

        # Stop the timer from repeating
        if self.pending_timer is not None:
            self.pending_timer.cancel()
            self.destroy_timer(self.pending_timer)
            self.pending_timer = None

        if not self.navigation_active:
            return

        start_pose = self.make_pose(5.5, -0.5, 3.14)
        #PLACEHOLDER DROP OFF POSE, MUST BE FOUND#
        end_pose = self.make_pose(2.97, -1.35, 0.174533)

        if not self.client.server_is_ready():
            self.fail_navigation('Nav2 server unavailable.')
            return

#Choose and send the correct navigation goal for the task
        if self.dropoff_task == False:
            start_pose.header.stamp = self.get_clock().now().to_msg()
            goal = NavigateToPose.Goal()
            goal.pose = start_pose
        elif self.dropoff_task == True:
            end_pose.header.stamp = self.get_clock().now().to_msg()
            goal = NavigateToPose.Goal()
            goal.pose = end_pose

        self.get_logger().info('Sending the navigation goal')

        future = self.client.send_goal_async(
            goal,
            feedback_callback=self.feedback_cb
        )

        future.add_done_callback(self.navigation_response_callback)

    def feedback_cb(self, fb):
        try:
            dist = fb.feedback.distance_remaining
            self.get_logger().info(f'Distance remaining: {dist:.2f} m')
        except Exception:
            pass  # ignore if feedback doesn't have distance

    def navigation_response_callback(self, future):

        try:
            handle = future.result()

            if not handle or not handle.accepted:
                self.fail_navigation('Nav2 position rejected.')
                return

            self.current_goal_handle = handle

            result_future = handle.get_result_async()
            result_future.add_done_callback(self.navigation_result_callback)

        except Exception as exc:
            self.fail_navigation(f'Position error: {exc}')

    def navigation_result_callback(self, future):

        try:
            result = future.result()
            self.current_goal_handle = None

            if result.status != GoalStatus.STATUS_SUCCEEDED:
                self.fail_navigation(
                    f'Nav2 failed: {result.status},'
                    f'Nav2 error: {result.result.error_code}'
                )
                return

            self.get_logger().info('Navigation goal reached successfully!')
            self.finish_navigation()

        except Exception as exc:
            self.fail_navigation(f'Result error: {exc}')


    def finish_navigation(self):
        self.navigation_running = False
        msg = Bool()
        msg.data = True
        self.completion_publisher.publish(msg)
        self.get_logger().info(
            'Robot has arrived'
        )
        self.dropoff_task = not self.dropoff_task # <-- Added for iteration

    def fail_navigation(self, message):
        self.navigation_running = False
        self.current_goal_handle = None
        self.get_logger().error(
            f'Navigation has stopped: {message}'
        )


def main(args=None):
    rclpy.init(args=args)

    node = HSWaypointNavigator()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()