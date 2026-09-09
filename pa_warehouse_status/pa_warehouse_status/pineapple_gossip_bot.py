import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class PineappleGossipBot(Node):
    def __init__(self):
        super().__init__('pineapple_gossip_bot') # Node name
        self.publisher_ = self.create_publisher(String, 'status_updates',10)
        timer_period = 2.0
        self.timer = self.create_timer(timer_period, self.timer_callback)
    
    def timer_callback(self):
        msg = String()
        msg.data = f"If you're seeing this, it's too late."
        self.publisher_.publish(msg)
        self.get_logger().info(f'Publishing: "{msg.data}"')





def main(args = None):
    print('Hi from pa_warehouse_status.')
    rclpy.init(args=args)
    pineapple_gossip_bot = PineappleGossipBot()
    rclpy.spin(pineapple_gossip_bot)
    pineapple_gossip_bot.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
