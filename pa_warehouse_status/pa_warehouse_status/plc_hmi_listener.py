import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class PLCHMIListener (Node):
    def __init__(self):
        super().__init__('plc_hmi_listener') # Node name
        self.subscription = self.create_subscription(String, 'hmi/unified_status',self.listener_callback,10)
    
    def listener_callback(self,msg):
        self.get_logger().info(f"PLC information: {msg.data}")
        



def main(args = None):
    print('PLC listener is up')
    rclpy.init(args=args)
    plc_hmi_listener = PLCHMIListener()
    rclpy.spin(plc_hmi_listener)
    plc_hmi_listener.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
