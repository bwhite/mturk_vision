import mturk_vision.server
import argparse


def main():
    # Parse command line
    parser = argparse.ArgumentParser(description="Serve ")
    parser.add_argument('data', help='Data URI')
    parser.add_argument('task_key', help='Unique task key used to prefix annotations')
    parser.add_argument('--setup', help='Initial data setup', action='store_true')
    parser.add_argument('--port', help='Run on this port',
                        default='8080')
    parser.add_argument('--redis_address', help='Redis server address',
                        default='localhost')
    parser.add_argument('--redis_port', help='Redis server port',
                        default=6379, type=int)
    parser.add_argument('--num_tasks', help='Number of tasks per worker',
                        default=100, type=int)
    parser.add_argument('--mode', help='Mode to run server in',
                        default='standalone', choices=['amt', 'standalone'])
    parser.add_argument('--type', help='Which AMT job type to run',
                        default='image_class', choices=['image_class'])
    args = vars(parser.parse_args())
    mturk_vision.server.server(**args)

if __name__ == "__main__":
    main()
