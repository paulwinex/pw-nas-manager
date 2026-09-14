import sys


def main():
    if "--version" in sys.argv:
        from nasmanager import __version__

        print(f"nasmanager {__version__}")
        return

    from nasmanager.ui.main import NasManagerApp

    app = NasManagerApp()
    app.run()


if __name__ == "__main__":
    main()