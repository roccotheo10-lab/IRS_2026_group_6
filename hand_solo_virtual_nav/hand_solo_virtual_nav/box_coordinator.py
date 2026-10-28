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
        
        self.subscription = self.create_subscription(String, 'hmi/unified_status',self.box_callback,10)
        self.completion_subscription = self.create_subscription(Bool, '/hs_arm/sequence_complete', self.sequence_complete_callback, 10)

        self.lifecycle_client = self.create_client(
            ChangeState,
            '/hs_arm/change_state'
        )
        self.activation_requested = False
        self.box_present = False
        self.get_logger().info('Waiting for box detection...')
        self.state_client = self.create_client(
            GetState,
            '/hs_arm/get_state'
        )

    def box_callback(self, msg):

        try:
            data = json.loads(msg.data)
            box = data["box"]

            weight = float(box['weight_raw'].replace(':', '').replace('kg', '').strip())
            if weight == 0:
                self.box_present = False
                return

        except (KeyError, TypeError, ValueError):
            return

        if self.box_present:
            return

        if self.activation_requested:
            return

        self.box_present = True

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

        # Prevent overlapping lifecycle requests.
        self.activation_requested = True

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
            else:
                self.activation_requested = False
                self.get_logger().error(
                    'Arm activation failed.'
                )

        except Exception as exc:
            self.activation_requested = False
            self.get_logger().error(str(exc))

    def sequence_complete_callback(self, msg):

        if not msg.data:
            return

        self.get_logger().info(
            'Pickup complete. Requesting arm deactivation.'
        )

        request = ChangeState.Request()
        request.transition.id = Transition.TRANSITION_DEACTIVATE

        future = self.lifecycle_client.call_async(request)
        future.add_done_callback(self.deactivation_result)

    def deactivation_result(self, future):

        try:
            response = future.result()

            if response.success:
                self.get_logger().info(
                    'Arm deactivated. Ready for next box.'
                )

                self.activation_requested = False

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