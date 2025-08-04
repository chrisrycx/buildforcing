'''
A utility script to get some information about the build forcing

This could potentially be used in a number of ways. Current implementation:
- Return the settings order for the build forcing
'''
from buildforcing.buildsite import SiteBuilder
import argparse

# Load some command line arguments:
# --settings_order
def main():
    parser = argparse.ArgumentParser(description='Get information about the build forcing settings order.')
    parser.add_argument('--settings_order', action='store_true', help='Print the settings order for the build forcing.')
    args = parser.parse_args()

    if args.settings_order:
        print(f"Settings order: {SiteBuilder.settings_order}")
    else:
        print("No arguments provided. Use --settings_order to get the settings order.")

if __name__ == '__main__':
    main()
