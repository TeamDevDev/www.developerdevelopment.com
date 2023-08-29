"""Minify all of the files in the project."""

import argparse
import os
import sys
from pathlib import Path

import csscompressor
import minify_html
import rjsmin
from rich.console import Console

console = Console()

DEFAULT_CONSOLE_STYLE = "bold blue"

source_directory_root = ""


def minify_files(source_directory: str, destination_directory: str) -> None:
    """Minify all of the files in the project directory."""
    # global source_directory_root
    # recursively iterate through all files and directories
    for current_file_name in os.listdir(source_directory):
        # create the current filename subject to analysis
        analysis_file_path = os.path.join(source_directory, current_file_name)
        # dealing with a file and thus it is a candidate
        # for the minification process
        if os.path.isfile(analysis_file_path):
            # create the current filename for writing to file system
            saving_file_path_str = analysis_file_path
            saving_file_path_str = saving_file_path_str.replace(
                source_directory_root, destination_directory
            )
            destination_path = Path(saving_file_path_str)
            # create the destination directory if it doesn't exist
            destination_path.parent.absolute().mkdir(parents=True, exist_ok=True)
            # extract the extension from this filename so
            # that the script can check if it is one of
            # the types of files that can be minified
            extension = os.path.splitext(current_file_name)[1].lower()
            # minify the CSS file
            if extension == ".css":
                try:
                    minified_content = csscompressor.compress(
                        open(analysis_file_path).read()
                    )
                    with open(saving_file_path_str, "w") as file:
                        file.write(minified_content)
                    console.print(f"CSS: Minifying {analysis_file_path}")
                    console.print(f"CSS: Savinmg {saving_file_path_str}")
                except ValueError:
                    console.print(f"CSS: Could not minifiy file {analysis_file_path}")
            # minify the HTML file
            elif extension == ".html":
                minified_content = minify_html.minify(
                    open(analysis_file_path).read(),
                    minify_js=True,
                    minify_css=True,
                    keep_comments=False
                )
                with open(saving_file_path_str, "w") as file:
                    file.write(minified_content)
                console.print(f"HTML: Minifying {analysis_file_path}")
                console.print(f"HTML: Saving {saving_file_path_str}")
            # minify the JS file
            elif extension == ".js":
                minified_content = str(rjsmin.jsmin(open(analysis_file_path).read()))
                with open(saving_file_path_str, "w") as file:
                    file.write(minified_content)
                console.print(f"JS: Minifying {analysis_file_path}")
                console.print(f"JS: Saving to {saving_file_path_str}")
            # do not have a minifier for a specific
            # file and thus this file should be skipped
            else:
                console.print(f"Skipping {analysis_file_path}")
        # found a directory, so recursively traverse into
        # so that minification process can continue until done;
        # keep using the same destination_directory as that will
        # not change during the recursive traversal process
        elif os.path.isdir(analysis_file_path):
            minify_files(analysis_file_path, destination_directory)


def main() -> None:
    """Perform the steps for the main function."""
    global source_directory_root
    # parse the command-line arguments using argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--source")
    parser.add_argument("-d", "--destination")
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    # create the argument parser
    args = parser.parse_args()
    # do not run the script unless quarto is rendering
    # all of the files (i.e., do not run during preview)
    if not os.getenv("QUARTO_PROJECT_RENDER_ALL") and not args.force:
        sys.exit()
    # define the default source directory that will contain
    # the contents that are going to be minified
    source_directory_path = "_site"
    # define the default destination directory that will
    # contain the minified contents
    destination_directory_path = "_site"
    # there is a directory for the source, so use it instead of
    # the default directory for the source
    if args.source is not None:
        source_directory_path = args.source
    # there is a directory for the destination, so use it instead of
    # the default directory for the destination
    if args.destination is not None:
        destination_directory_path = args.destination
    # provide the debugging information
    if args.verbose is True:
        console.print(
            f":clap: Using the source directory of {destination_directory_path}\n",
            style=DEFAULT_CONSOLE_STYLE,
        )
        console.print(
            f":clap: Using the source directory of {source_directory_path}\n",
            style=DEFAULT_CONSOLE_STYLE,
        )
    # define the global source directory root
    source_directory_root = source_directory_path
    # perform the minification of all of the files
    # inside of the directory; note that this is
    # a destructive operation that changes the
    # contents of the specified directory
    minify_files(source_directory_path, destination_directory_path)


if __name__ == "__main__":
    # run the main function
    # that controls all of the parsing
    # of the bibliography entries
    main()
