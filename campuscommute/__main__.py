"""Run the dashboard: python -m campuscommute [--host HOST] [--port PORT] [--db PATH]"""

import argparse
from pathlib import Path

from .server import create_server


def main():
    parser = argparse.ArgumentParser(description="CampusCommute shuttle demand dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default="data/campuscommute.db", help="SQLite database path")
    args = parser.parse_args()

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    server = create_server(args.db, args.host, args.port)
    print(f"CampusCommute running at http://{args.host}:{args.port}  (database: {args.db})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
