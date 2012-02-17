import argparse
import mturk_vision


def main():
    # Parse command line
    parser = argparse.ArgumentParser(description="Serve ")
    parser.add_argument('--port', help='Run on this port',
                        default='8080')
    parser.add_argument('--num_tasks', help='Number of tasks per worker (unused in standalone mode)',
                        default=100, type=int)
    parser.add_argument('--mode', help='Number of tasks per worker',
                        default='standalone', choices=['amt', 'standalone'])
    parser.add_argument('--type', help='Which AMT job type to run',
                        default='label', choices=['label', 'match', 'description'])
    parser.add_argument('--data', help='Path to the data directory', default='data')
    parser.add_argument('--db', help='Path to the database directory', default='~/amt_video/')
    args = vars(parser.parse_args())
    mturk_vision.server(**args)

if __name__ == "__main__":
    main()
