import os
import subprocess
import sys


def setup_environment():
    """Setup the Replit environment"""
    print("Setting up environment...")

    # Install dependencies
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    # Create .env file if it doesn't exist
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write(
                f"HOSTNAME={os.environ.get('REPL_SLUG')}.{os.environ.get('REPL_OWNER')}.repl.co\n"
            )
            f.write("FLASK_APP=server.app\n")
            f.write("FLASK_ENV=production\n")


def main():
    print("Starting deployment to Replit...")

    # Setup environment
    setup_environment()

    print("\nDeployment complete!")
    print("\nNext steps:")
    print("1. Run 'python publish_feed.py' to publish your feed")
    print("2. Copy the Feed URI and set it as DAILY_SEO_FEED_URI in .env")
    print("3. Click 'Run' in Replit to start the server")
    print("\nYour feed will be available at:")
    print(
        f"https://{os.environ.get('REPL_SLUG')}.{os.environ.get('REPL_OWNER')}.repl.co"
    )


if __name__ == "__main__":
    main()
