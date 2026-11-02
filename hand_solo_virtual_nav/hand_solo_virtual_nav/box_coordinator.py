import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_msgs.msg import Bool
from lifecycle_msgs.srv import ChangeState, GetState
from lifecycle_msgs.msg import Transition, State
import json


class BoxLifecycleCoordinator(Node):

    def __init__(self):
        super().__init__('box_lifecycle_coordinator')
        
        self.subscription = self.create_subscription(String, 'hmi/unified_status',self.box_callback,10) #Subscribe to receive PLC info
        self.completion_subscription = self.create_subscription(Bool, '/hs_arm/sequence_complete', self.sequence_complete_callback, 10) #Subscribe to receive manipulator info
        self.navigation_completion_subscription = self.create_subscription(Bool, '/hs_navigation/sequence_complete', self.navigation_complete_callback,10) #Subscribe to receive navigation info
        # Communicate state transitions through service clients
        self.lifecycle_client = self.create_client(ChangeState, '/hs_arm/change_state')
        self.nav_lifecycle_client = self.create_client(ChangeState, '/hs_navigation/change_state')
        
        self.activation_requested = False
        self.box_present = False
        self.get_logger().info('Waiting for box detection...')
        # Get lifecycle information
        self.state_client = self.create_client(GetState, '/hs_arm/get_state')
        self.nav_state_client = self.create_client(GetState, '/hs_navigation/get_state')
        # Initial state
        self.current_state = 'navigate_to_pickup'
        # Wait five seconds to send initial activation request
        self.startup_timer = self.create_timer(5.0, self.start_navigation)

    def start_navigation(self):
        # Check if navigation services are ready
        if not self.nav_lifecycle_client.service_is_ready():
            return

        if not self.nav_state_client.service_is_ready():
            return

        self.startup_timer.cancel() # cancels timer once the nav services are ready
        # Request the navigation lifecycle state
        request = GetState.Request()
        future = self.nav_state_client.call_async(request)
        future.add_done_callback(self.check_nav_state)

    def check_nav_state(self, future):

        try:
            response = future.result()

            if response.current_state.id != State.PRIMARY_STATE_INACTIVE:
                self.get_logger().warn(
                    'Nav not ready for activation. '
                    f'Current state: {response.current_state.label}'
                )
                return

            self.get_logger().info(
                'Nav is inactive. Requesting activation.'
            )
            # Requests activation of navigation node
            request = ChangeState.Request()
            request.transition.id = Transition.TRANSITION_ACTIVATE
            activation_future = self.nav_lifecycle_client.call_async(request)
            activation_future.add_done_callback(self.nav_activation_result)

        except Exception as exc:
            self.get_logger().error(str(exc))

    def nav_activation_result(self, future):
        # Gets the result of activating the navigation
        try:
            response = future.result()

            if response.success:
                self.get_logger().info(
                    'Navigation activated successfully'
                )
            else:
                self.get_logger().error(
                    'Nav activation failed.'
                )

        except Exception as exc:
            self.get_logger().error(str(exc))


    def box_callback(self, msg):
        # Uses the JSON parsing to isolate the raw weight string
        try:
            data = json.loads(msg.data)
            box = data["box"]
            # Stripping unnecessary information is needed
            weight = float(box['weight_raw'].replace(':', '').replace('kg', '').strip())
            if weight <= 0:
                self.box_present = False
                return

        except (KeyError, TypeError, ValueError):
            return
        
        if self.current_state != 'wait_for_box':
            return

        if self.box_present:
            return

        if self.activation_requested:
            return

        if not self.lifecycle_client.service_is_ready():
            self.get_logger().warn(
                'Arm lifecycle service unavailable.'
            )
            return

        if not self.state_client.service_is_ready():
            self.get_logger().warn(
                'Arm state service unavailable.'
            )
            return
        
        self.box_present = True

        # Prevent overlapping lifecycle requests.
        self.activation_requested = True

        # request the arm lifecycle node state to begin process of picking up box
        request = GetState.Request()
        future = self.state_client.call_async(request)
        future.add_done_callback(self.check_arm_state)


    def check_arm_state(self, future):

        try:
            response = future.result()

            if response.current_state.id != State.PRIMARY_STATE_INACTIVE:
                self.get_logger().warn(
                    'Arm not ready for activation. '
                    f'Current state: {response.current_state.label}'
                )
                self.activation_requested = False
                return

            self.get_logger().info(
                'Arm is inactive. Requesting activation.'
            )
            # Requests the activation of the arm lifecycle node
            request = ChangeState.Request()
            request.transition.id = Transition.TRANSITION_ACTIVATE
            activation_future = self.lifecycle_client.call_async(request)
            activation_future.add_done_callback(self.activation_result)

        except Exception as exc:
            self.activation_requested = False
            self.get_logger().error(str(exc))


    def activation_result(self, future):

        try:
            response = future.result()

            if response.success:
                self.get_logger().info(
                    'Box detected: arm activated!'
                )
                if self.current_state == 'wait_for_box': #Transitions to next state of loop
                    self.current_state = 'pickup_box'
            else:
                self.activation_requested = False
                self.get_logger().error(
                    'Arm activation failed.'
                )

        except Exception as exc:
            self.activation_requested = False
            self.get_logger().error(str(exc))

        
    def navigation_complete_callback(self,msg):

        if not msg.data:
            return
        
        self.get_logger().info('Navigation has been completed')

        # requests deactivation of navigation lifecycle node        
        request = ChangeState.Request()
        request.transition.id = Transition.TRANSITION_DEACTIVATE
        future = self.nav_lifecycle_client.call_async(request)
        future.add_done_callback(self.nav_deactivation_result)

    def nav_deactivation_result(self, future):
        # retireves result of attempted nav deactivation
        try:
            response = future.result()

            if response.success:
                self.get_logger().info(
                    'Nav deactivated.'
                )
                # if successful, the current state variable progresses to next state in loop
                if self.current_state == 'navigate_to_pickup': 
                    self.current_state = 'wait_for_box'
                    self.get_logger().info('Arrived at pickup. Waiting for box detection.')

                elif self.current_state == 'navigate_to_dropoff':
                    self.current_state = 'place_box'
                    self.get_logger().info('Arrived at drop-off spot. Activating arm for placement.')
                    # requests arm lifecycle node state, beginning communication for box drop off
                    request = GetState.Request()
                    future = self.state_client.call_async(request)
                    future.add_done_callback(self.check_arm_state)

            else:
                self.get_logger().error(
                    'Nav deactivation failed.'
                )

        except Exception as exc:
            self.get_logger().error(str(exc))

    def sequence_complete_callback(self, msg):

        if not msg.data:
            return

        self.get_logger().info(
            'Pickup complete. Requesting arm deactivation.'
        )
        # requests deactivation of arm lifecycle node
        request = ChangeState.Request()
        request.transition.id = Transition.TRANSITION_DEACTIVATE
        future = self.lifecycle_client.call_async(request)
        future.add_done_callback(self.deactivation_result)

    def deactivation_result(self, future):
        # checks for result of attempting to deactivate the arm node
        try:
            response = future.result()
            # If the deactivation is successful, the current state variable progresses to next state of loop
            if response.success:
                self.get_logger().info(
                    'Arm deactivated. Ready for next box.')
                self.activation_requested = False
                if self.current_state == 'pickup_box':
                    self.current_state = 'navigate_to_dropoff'
                    self.get_logger().info('Pickup complete. Navigating to drop-off.')
                    # starts the process of navigation again
                    self.start_navigation()

                elif self.current_state == 'place_box': # if true, restarts loop by returning to belt
                    self.current_state = 'navigate_to_pickup'
                    self.get_logger().info('Placement complete. Returning to conveyor belt.')
                    # starts the process of navigation again
                    self.start_navigation()

            else:
                self.get_logger().error(
                    'Arm deactivation failed.'
                )

        except Exception as exc:
            self.get_logger().error(str(exc))


def main(args=None):
    rclpy.init(args=args)
    node = BoxLifecycleCoordinator()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()