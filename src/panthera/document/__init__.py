#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2021 - 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Wrapper class for building the docs.

The output of running these tools will be generated in docs_build at the root of this project.
Note - You should not run this script directly (due to path issues).
Please run it through the `tools/build_docs` sh script.
"""

from __future__ import annotations

import abc
import dataclasses
import logging
import os
import pathlib
import re
import shutil

from ..toolchain import Annotation, ToolChain

TOP_LEVEL_FILES_LINK_NAME: str = "top_level_md_files"

SOURCE_MEWBOT_DIR: str = "source_mewbot"
SOURCE_EXAMPLES_DIR: str = "source_examples"

TOP_LEVEL_FILES_NEED_TITLE: dict[str, bool] = {
    "code_of_conduct.md": False,
    "contributing.md": False,
    "contributors.md": False,
    "readme.md": False,
}

COPY_EXCEPTIONS: tuple[str, ...] = ()

OUTPUT_TARGET_LIST: tuple[str, ...] = ("html",)

SRC_APIS_TO_DOC: tuple[str, ...] = ("mewbot", "examples")
# docs for the "plugins" folder also have to be build - dealt with in own method
TOP_LEVEL_APIS_TO_DOC: tuple[str, ...] = ("tests",)


@dataclasses.dataclass
class DocPaths:
    """
    Stores the paths relevant to the construction of the docs.
    """

    _repo_dir: str

    @property
    def repo_dir(self) -> str:
        """
        Access method for the root dir of the repo.

        :return:
        """
        return self._repo_dir

    @repo_dir.setter
    def repo_dir(self, value: str) -> None:
        """
        Set this to set all the other path properties.

        :param value:
        :return:
        """
        self._repo_dir = value

    @property
    def docs_dir(self) -> str:
        """
        The docs folder within the repo.

        :return:
        """
        return os.path.join(self._repo_dir, "docs")

    @docs_dir.setter
    def docs_dir(self, value: str) -> None:
        raise NotImplementedError(
            "Cannot set docs_dir directly - please set repo_dir instead"
        )

    @property
    def docs_build_dir(self) -> str:
        """
        The docs build folder within the repo.

        :return:
        """
        return os.path.join(self._repo_dir, "docs_build")

    @docs_build_dir.setter
    def docs_build_dir(self, value: str) -> None:
        raise NotImplementedError(
            "Cannot set docs_build_dir directly - please set repo_dir instead"
        )

    @property
    def top_level_files_link_dir(self) -> str:
        """
        Dir within the build dir which contains refs to files in the root of the repo.

        Way to include files such as the top level "README.md", "CODE_OF_CONDUCT.md" e.t.c in the
        docs.
        :return:
        """
        return os.path.join(self.docs_build_dir, TOP_LEVEL_FILES_LINK_NAME)

    @top_level_files_link_dir.setter
    def top_level_files_link_dir(self, value: str) -> None:
        raise NotImplementedError(
            "Cannot set top_level_files_link_dir directly - please set repo_dir instead"
        )


class ApiBuildTool(ToolChain, abc.ABC):
    """
    The API tooling.

    This is intended for automatic generation of docs for the api.
    """

    _logger: logging.Logger

    doc_paths: DocPaths = DocPaths(_repo_dir="")

    def ensure_docs_build_folder(self) -> None:
        """
        Create, if needed, the "docs_build" folder in the repo as a copy of "docs".

        If "docs_build" exists - it will be removed.
        It will be replaced with a copy of "docs".
        In which we will operate to build the docs.
        :return:
        """
        if os.path.exists(self.doc_paths.docs_build_dir):
            self._logger.info(
                "docs build dir exists at %s - removing", self.doc_paths.docs_build_dir
            )
            shutil.rmtree(self.doc_paths.docs_build_dir)

        shutil.copytree(src=self.doc_paths.docs_dir, dst=self.doc_paths.docs_build_dir)

        os.mkdir(os.path.join(self.doc_paths.docs_build_dir, "_static"))

        # Ensure the folder which will hold the links to the top level files
        if os.path.exists(self.doc_paths.top_level_files_link_dir):
            shutil.rmtree(self.doc_paths.top_level_files_link_dir)
        os.mkdir(self.doc_paths.top_level_files_link_dir)

    def build_api_docs(self) -> None:
        """
        Construct the api docs.

        This will build api docs for all the modules in
        :py:func:`mewbot.tools.docs.DocToolchain.apis_to_doc`.
        :return:
        """
        self._logger.info("Constructing docs for module APIs")

        for target_module in SRC_APIS_TO_DOC:
            self._generate_module_index_files(
                target_module=target_module, src=True, implicit_namespaces=True
            )

        for target_module in TOP_LEVEL_APIS_TO_DOC:
            self._generate_module_index_files(
                target_module=target_module, src=False, implicit_namespaces=True
            )

        self._generate_plugin_api_docs()

    def _generate_plugin_api_docs(self) -> None:
        """
        Specific method for automatically documenting the plugin folder.

        Sphinx seems to be having a bad time generating docs for namespace plugins.
        Thus need to employ some substitution techniques, so it can actually find the right modules.
        :return:
        """
        # Generate the raw documentation
        self._generate_module_index_files(
            target_module="plugins", src=False, implicit_namespaces=True
        )

        # Turns out, api-doc _does not_ like namespace plugins
        # So need to re-write some files

        # Go through and re-write the documentation using correct module references
        source_plugins_dir = os.path.join(self.doc_paths.docs_build_dir, "source_plugins")
        assert os.path.exists(
            source_plugins_dir
        ), f"{source_plugins_dir=} not found - cannot build"

        self._logger.info("Starting plugin refactor")
        for src_file in os.listdir(source_plugins_dir):
            src_file_path = os.path.join(source_plugins_dir, src_file)

            # Read the file into memory - modify it - dump it back
            with open(src_file_path, "r", encoding="utf-8") as src_file_in:
                src_file_lines = src_file_in.readlines()

            # Need to repoint several of the modules _slightly_ differently
            dst_file_lines = []
            for file_line in src_file_lines:
                if not file_line.startswith(".. automodule:: "):
                    dst_file_lines.append(file_line)
                    continue

                # Desired behavior
                # ".. automodule:: plugins.mewbot-io-discord.src.examples.discord_bots"
                # maps to
                # ".. automodule:: examples.discord_bots"
                # e.t.c
                if re.match(
                    r"^\.\. automodule:: plugins\.[a-z0-9-A-Z]+\.src\..*$", file_line
                ):
                    new_line = re.sub(
                        r"plugins\.[a-z0-9-A-Z]+\.src\.", "", file_line, count=1
                    )
                    dst_file_lines.append(new_line)
                    self._logger.info(
                        "Entry line of file %s changed from \n%s\n->\n%s",
                        src_file,
                        file_line,
                        new_line,
                    )
                    continue

            # Now write it back
            with open(src_file_path, "w", encoding="utf-8") as src_file_out:
                src_file_out.writelines(dst_file_lines)

    def _generate_module_index_files(
        self, target_module: str, src: bool, implicit_namespaces: bool
    ) -> None:
        """
        Generate index files for the given module.

        :param target_module: The module to document
        :param src: Is the module in the root of the repo or the `src` folder.
        :return:
        """
        self._logger.info("Constructing docs for %s in src - %s", target_module, src)

        args = ["sphinx-apidoc"]

        module_folder_name = f"source_{target_module}"
        module_folder = os.path.join(self.doc_paths.docs_build_dir, module_folder_name)

        if src:
            target_module_path = os.path.join(self.doc_paths.repo_dir, "src", target_module)
        else:
            target_module_path = os.path.join(self.doc_paths.repo_dir, target_module)

        assert os.path.exists(target_module_path), f"{target_module_path=} does not exist!"

        args.extend(
            [
                "-o",
                module_folder,
                target_module_path,
            ]
        )
        if implicit_namespaces:
            args.extend(["--implicit-namespaces"])

        self.run_tool(f"Sphinx APIdoc (for {target_module})", *args)

        self.generate_source_index(module_folder_name)

    def generate_source_index(self, src_folder_name: str) -> None:
        """
        Assists auto-generation of documentation from doc strings of entire modules.

        sphinx has an inbuilt script for iteratively generating documentation from the doc strings
        of entire modules.
        However, it doesn't have a good means of generating index files for this auto-generated
        files so you can include them more easily in the docs.
        This function generates that index file, which can then be included in the toc for the
        master index file.

        :param src_folder_name:

        :return:
        """

        src_dir_paths: list[str] = []
        for file_name in os.listdir(
            os.path.join(self.doc_paths.docs_build_dir, src_folder_name)
        ):
            src_dir_paths.append(src_folder_name + "/" + os.path.splitext(file_name)[0])

        index_str = "   " + "\n   ".join(src_dir_paths)

        src_files_index_file_path = os.path.join(
            self.doc_paths.docs_build_dir, f"{src_folder_name}_index.rst"
        )

        if os.path.exists(src_files_index_file_path):
            os.unlink(src_files_index_file_path)

        with open(src_files_index_file_path, "w", encoding="utf-8") as src_index_file:
            # rst files need particular numbers of spaces - so can't use textwrap.dedent
            src_index_file_contents = f"""

..
  NOTE - THIS IS AN AUTO-GENERATED FILE - CHANGES MADE HERE WILL NOT PERSIST!


.. toctree::
   :maxdepth: 4
   :caption: {src_folder_name} file index:

{index_str}

            """

            src_index_file.write(src_index_file_contents)


class IndexGenerationTools:
    """
    Tools to build index files for the other docs.
    """

    _logger: logging.Logger

    doc_paths: DocPaths = DocPaths(_repo_dir="")

    _top_level_files_link_dir: str

    @property
    def repo_folder(self) -> str:
        """
        Returns the root folder of the mewbot repo.

        :return:
        """
        return self.doc_paths.repo_dir

    @repo_folder.setter
    def repo_folder(self, value: str) -> None:
        raise NotImplementedError("repo_folder cannot be set directly")

    def generate_top_level_md_files_index(self) -> None:
        """
        Generate include objects for the .md files at the top level of the directory.

        The top level files are included via bridge files
        These are rst files in the top level which include the md files themselves in the directory
        root.
        The reason it was done this way was because you _cannot_ directly include an object into
        the contents tree, but you _can_ include a rst document which include the entire,
        translated, md file.

        Some of these files do not include things which are recognizable titles.
        So titles need to be added to some files. But not others.
        This is what the `TOP_LEVEL_FILES_NEED_TITLE` constant is for - do the generated files
        need a title?
        """

        valid_index_files: list[str] = []
        for file_name in self._get_sorted_top_level_files():
            # Also copy any images from the top level into the link dir
            if os.path.splitext(file_name)[1].lower() in (".svg", ".tff", ".jpg"):
                new_image_path = os.path.join(
                    self.doc_paths.top_level_files_link_dir, file_name
                )
                shutil.copy(os.path.join(self.repo_folder, file_name), new_image_path)

            if os.path.splitext(file_name)[1].lower() != ".md":
                continue

            file_name_token = os.path.splitext(file_name)[0]
            ref_file_path = os.path.join(
                self.doc_paths.top_level_files_link_dir, f"main_{file_name_token.lower()}.rst"
            )

            if os.path.exists(ref_file_path):
                os.unlink(ref_file_path)

            file_title_status = TOP_LEVEL_FILES_NEED_TITLE.get(file_name.lower(), True)

            self._write_reference_file(
                ref_file_path=ref_file_path,
                file_name=file_name,
                file_title_status=file_title_status,
            )

            abs_path = os.path.splitext(ref_file_path)[0]

            strip_len = len(self.doc_paths.docs_build_dir) + 1
            valid_index_files.append(abs_path[strip_len:])

        # Process valid_index_files into an OS agnostic form
        new_valid_index_files: list[str] = []
        for file_path in valid_index_files:
            file_tokens = file_path.split(os.sep)
            new_valid_index_files.append("/".join(file_tokens))

        valid_index_files = new_valid_index_files

        index_str = "   " + "\n   ".join(valid_index_files)

        with open(
            os.path.join(self.doc_paths.docs_build_dir, "main_files_index.rst"),
            "w",
            encoding="utf-8",
        ) as main_files_index:
            main_files_index.write(
                f"""
..
  NOTE - THIS IS AN AUTO-GENERATED FILE - CHANGES MADE HERE WILL NOT PERSIST!

.. toctree::
   :maxdepth: 4
   :caption: Top Level MD files:

{index_str}

    """
            )

    def _get_sorted_top_level_files(self) -> list[str]:
        """
        Return the top level file paths - sorted so that README.md is first.

        There may also be other requirements, but that's the most important.
        :return:
        """
        top_level_files = os.listdir(self.doc_paths.repo_dir)

        assert (
            "README.md" in top_level_files
        ), f"README.md not found in the projects root! {top_level_files}"

        # Shuffle README.md to the front of the list, so it'll be displayed at the top
        top_level_files.remove("README.md")
        top_level_files = [
            "README.md",
        ] + top_level_files

        return top_level_files

    @staticmethod
    def _write_reference_file(
        ref_file_path: str, file_name: str, file_title_status: bool
    ) -> None:
        """
        Write out a reference file pointing to a file at the top of the repo.

        :param ref_file_path:
        :param file_name:
        :param file_title_status:
        :return:
        """

        fn_title_emph_str = "=" * len(file_name)

        with open(ref_file_path, "w", encoding="utf-8") as fn_ref_file:
            if file_title_status:
                fn_ref_file.write(
                    f"""..
    Note - this is an auto generated file! All changes may be randomly lost!

{file_name}
{fn_title_emph_str}

.. mdinclude:: ../../{file_name}
                        """
                )

            else:
                fn_ref_file.write(
                    f"""..
    Note - this is an auto generated file! All changes may be randomly lost!

.. mdinclude:: ../../{file_name}
                                            """
                )

    def generate_all_docs_subfolder_indices(self) -> None:
        """
        Generate index files for all the subfolders of the form "[NAME]-docs" in "docs".

        :return:
        """
        for entry_name in os.listdir(self.doc_paths.docs_build_dir):
            entry_path = os.path.join(self.doc_paths.docs_build_dir, entry_name)
            if not os.path.isdir(entry_path):
                continue

            if not entry_path.endswith("-docs"):
                continue

            self.generate_docs_subfolder_index(docs_folder=entry_name)

    def generate_docs_subfolder_index(self, docs_folder: str) -> None:
        """
        Generates an index file so a docs tree (e.g. design-docs) can be included in the toc.

        :param docs_folder: A folder in "docs" to include in the build.
        :return:
        """
        self._logger.info("Generating index files for docs_folder %s", docs_folder)

        valid_file_paths = []
        for root, _, files in os.walk(
            os.path.join(self.doc_paths.docs_build_dir, docs_folder)
        ):
            for file_name in files:
                if os.path.splitext(file_name)[1].lower() != ".md":
                    continue

                abs_path = os.path.join(root, file_name)
                rel_path_length = len(self.doc_paths.docs_build_dir) + 1
                doc_rel_path = abs_path[rel_path_length:]

                valid_file_paths.append(doc_rel_path)

            self._build_index_file(docs_folder=docs_folder, valid_file_paths=valid_file_paths)

    def _build_index_file(self, docs_folder: str, valid_file_paths: list[str]) -> None:
        """
        Write the master index file out.

        :param docs_folder:
        :param valid_file_paths:
        :return:
        """
        # Process valid_index_files into an OS agnostic form
        files_in_index = ["/".join(path.split(os.sep)) for path in valid_file_paths]
        index_str = "   " + "\n   ".join(files_in_index)

        # Caption string which will be used to name this toc
        # Take each folder name segment, put it in title case.
        name = " ".join(_.title() for _ in docs_folder.split("-"))

        # Gen the index name and remove it if it exists already
        index_file_path = os.path.join(
            self.doc_paths.docs_build_dir, f"{docs_folder}-index.rst"
        )
        if os.path.exists(index_file_path):
            os.unlink(index_file_path)

        # Write the index file out
        with open(index_file_path, "w", encoding="utf-8") as main_files_index:
            main_files_index.write(
                f"""
..
  NOTE - THIS IS AN AUTO-GENERATED FILE - CHANGES MADE HERE WILL NOT PERSIST!

.. toctree::
   :maxdepth: 4
   :caption: {name}:

{index_str}
                    """
            )


class DocToolchain(ApiBuildTool, IndexGenerationTools):
    """
    Wrapper class for building the mewbot docs.

    By default, builds docs from the "docs" folder in the root of this repo.
    Output is generated in a "docs_build" folder in the root of this repo.

    WARNING - the "docs_build" folder will be deleted during this process.
    This folder is entirely generated and managed by this script.
    Do not make changes to it - these will not persist.
    Instead, make changes in the "docs" folder.

    NOTE - in the docs folder, you might see reference to some files which do not, there, exist.
    This is because some of them are auto-generated.
    It seemed unwise to mingle the auto-generated and human generated doc files.
    As such, all the files are copied into "docs_build" before the build is run.

    Will be improved to allow easier build of plugin docs in the future.
    """

    _logger: logging.Logger

    _repo_dir: str
    _docs_dir: str
    _docs_build_dir: str

    _top_level_files_link_dir: str

    def __init__(self, *folders: str, in_ci: bool) -> None:
        """
        Sets up a tool chain with the given settings for docs build.

        :param folders: The list of folders to run this tool against
        :param in_ci: Whether this is a run being called from a CI pipeline
        """
        super().__init__(*folders, in_ci=in_ci)

        self._logger = logging.getLogger("DocsBuildLogger")

    def run(self) -> list[Annotation]:
        """
        Run the doc build tools in sequences.

        Executes
         - :py:func:`mewbot.tools.docs.DocToolchain.validate_docs_folder`

        :return:
        """
        self._logger.info("Run has been called - starting docs build")

        self.set_paths()

        self.generate_dependency_chart()

        self.ensure_docs_build_folder()

        # Build the automated index files
        # - for the top level files in the repo - README.md etc
        self.generate_top_level_md_files_index()
        # - for the program api
        self.build_api_docs()
        # - for all other folder in the tree
        self.generate_all_docs_subfolder_indices()

        # With the build folder prepared, actually preform a build of the docs
        self.build_the_docs()

        return []

    def set_paths(self) -> None:
        """
        Checks that we have a "repo" and "docs" folder in the expected place.

        NOTE - the default build folder "docs_build" in the repo root folder - is in .gitignore.
        Please do not commit docs to the main mewbot repo -
        :return:
        """
        # Determine the path to the repo we're running in
        repo_base_folder = str(pathlib.Path(os.curdir).absolute())

        if not os.path.exists(repo_base_folder):
            self._logger.error(
                "Cannot run - repo_base_folder - %s - does not exist. "
                "You might be running from a compiled object",
                repo_base_folder,
            )
            raise NotADirectoryError

        src_base_folder = os.path.join(repo_base_folder, "src")

        if not os.path.exists(src_base_folder):
            self._logger.error(
                "Cannot run - src folder - %s - does not exist. "
                "You might be running from a compiled object",
                repo_base_folder,
            )
            raise NotADirectoryError(f"{repo_base_folder=} does not exist!")

        self._logger.info("Repo base folder detected as %s", repo_base_folder)
        # This sets the "docs" and "docs_build" paths
        self.doc_paths.repo_dir = repo_base_folder

        # Also need to check docs folder - from which the actual documentation
        # will be read before build
        assert os.path.exists(
            self.doc_paths.docs_dir
        ), f"{self.doc_paths.docs_dir=} does not exist! Nothing to build!"

    def generate_dependency_chart(self) -> None:
        """Build an SVG dependency chart with pydeps."""

        self.run_tool(
            "Dependncy Chart",
            "pydeps",
            "-o",
            "mewbot.svg",
            "--no-show",
            "--cluster",
            "--reverse",
            "--rankdir",
            "TB",
            "--rmprefix",
            "mewbot",
            "-xx",
            "mewbot.api",
            "-x",
            "mewbot.tools.*",
            "mewbot.test",
            "--",
            folders={"src/mewbot"},
        )

    def build_the_docs(self) -> None:
        """
        Preform a build for all build targets.

        :return:
        """
        for build_target in OUTPUT_TARGET_LIST:
            args = ["sphinx-build"]

            # Extend with the target we are actually using for this build
            args.extend(["-b", build_target])

            # Extend with the build directories
            target_build_dir = os.path.join(
                self.doc_paths.docs_build_dir, "_build", build_target
            )
            args.extend([self.doc_paths.docs_build_dir, target_build_dir])

            # Execute
            self.run_tool(f"Building docs {build_target}", *args)


if __name__ == "__main__":
    doc_builder = DocToolchain(in_ci=False)
    doc_builder()
