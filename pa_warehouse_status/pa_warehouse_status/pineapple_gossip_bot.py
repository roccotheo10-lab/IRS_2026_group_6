import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class PineappleGossipBot(Node):
    def __init__(self):
        super().__init__('pineapple_gossip_bot')
        self.publisher_ = self.create_publisher(String, 'status_updates',10)
        timer_period = 2.0
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 1
    
    def timer_callback(self):
        msg = String()
        msg.data = f"Scanning page {self.i} of phone book.\nStatus: Sarah Connor not found"
        self.publisher_.publish(msg)
        self.get_logger().info(f'Publishing: "{msg.data}"')
        self.i += 1





def main(args = None):
    print('Hi from pa_warehouse_status.')
    rclpy.init(args=args)
    pineapple_gossip_bot = PineappleGossipBot()
    rclpy.spin(pineapple_gossip_bot)
    pineapple_gossip_bot.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
