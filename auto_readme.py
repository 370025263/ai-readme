# Author: Lintao
import argparse
import fnmatch
import json
import logging
import os
from llm_api import get_model_answer

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class AutoReadme:
    """
    AutoReadme is a tool that automatically generates README files and dependencies, e.g., project structure and requirements.txt, for a given project directory.
    """

    def __init__(self, project_name, project_dir, author, author_info=None, model_name=None,
                 out_put_dir=None, project_description=None, config_dir=None, language="en"):
        self.project_name = project_name
        self.project_dir = project_dir
        self.project_description = project_description
        self.project_author = author
        self.project_author_info = author_info
        self.language = language
        if not model_name:
            model_name = "gpt-4o"

        if out_put_dir is None:
            out_put_dir = os.path.join(ROOT_DIR, 'output', project_name).__str__()
            os.makedirs(out_put_dir, exist_ok=True)
        readme_path = os.path.join(out_put_dir, "README.md")
        if not config_dir:
            config_dir = os.path.join(ROOT_DIR, "config")
            os.makedirs(config_dir, exist_ok=True)

        self.config_dir = config_dir
        self.model = model_name
        self.out_put_dir = out_put_dir
        self.readme_path = readme_path
        logging.info(
            f"AutoReadme initialized for {project_name}, project directory: {project_dir}, Author: {author}, Config directory: {config_dir}, Model: {model_name}")

    def generate_dependency(self):
        logging.info(f"Generating project structure...")
        project_structure = self.generate_project_structure(self.project_dir)
        logging.debug(f'Project structure:')
        logging.debug("\n" + "\n".join(project_structure))
        save_content_to_file("\n".join(project_structure), os.path.join(self.out_put_dir, "PROJECT_STRUCTURE.md"))

        requirements = self.generate_project_requirements()
        logging.debug(f'Project requirements:')
        logging.debug("\n".join(requirements))
        save_content_to_file("\n".join(requirements), os.path.join(self.out_put_dir, "requirements.txt"))

        scripts_description = self.generate_description_of_all_scripts()
        logging.debug(f'Scripts description:')
        logging.debug(scripts_description)
        with open(os.path.join(self.out_put_dir, "SCRIPT_DESCRIPTION.json"), "w", encoding='utf-8') as f:
            json.dump(scripts_description, f, ensure_ascii=False, indent=4)
        logging.info(f"Dependencies have been generated and saved to {self.out_put_dir}")

    def load_ignore_files(self):
        logging.info("Loading ignore files")
        ignore_files = []
        gitignore_path = os.path.join(self.project_dir, ".gitignore")
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                for line in f:
                    if line and not line.startswith('#'):
                        line = line.strip().lstrip("/")
                        if line.endswith("/"):
                            line += "*"
                        ignore_files.append(line)
        logging.info(f".gitignore patterns: {ignore_files}")
        return ignore_files

    def is_ignored(self, filepath, ignore_files):
        relative_path = os.path.relpath(filepath, self.project_dir)  # get the relative path of the file
        if any(part.startswith('.') for part in filepath.split('/')) or "__pycache__" in relative_path:
            logging.debug(f"Ignored: {relative_path}")
            return True
        for pattern in ignore_files:
            if fnmatch.fnmatch(relative_path, pattern):
                logging.debug(f"Ignored: {relative_path}")
                return True
        logging.debug(f"Not ignored: {relative_path}")
        return False

    def find_all_scripts_and_config_files(self):
        logging.info(f"Finding all scripts in {self.project_dir}")
        ignore_files = self.load_ignore_files()
        scripts = []
        for root, dirs, files in os.walk(self.project_dir):
            for file in files:
                filepath = os.path.join(root, file)
                if not self.is_ignored(filepath, ignore_files):
                    if ((file.endswith(".py") or file.endswith(".sh") or file.endswith(".bash") or
                         (file.endswith(".json") and "config" in root.lower()))
                            and os.path.isfile(filepath)):
                        scripts.append(filepath)
        logging.info(f"Found {len(scripts)} scripts")
        for script in scripts:
            logging.debug(script)
        return scripts

    def generate_description_of_all_scripts(self):
        logging.info("Generating description of all scripts...")
        scripts = self.find_all_scripts_and_config_files()
        script_description = {}
        for script in scripts:
            description = self.generate_file_description(script)
            script_description[script] = description
            brief_start = str(description)[:20].replace('\n', '')
            brief_end = str(description)[-20:].replace('\n', '')
            logging.info(f"Description of {script}: {brief_start}...{brief_end}")
        return script_description

    def generate_project_structure(self, dir_path, indent_level=0, ignore_files=None):
        if ignore_files is None:
            ignore_files = self.load_ignore_files()

        markdown_lines = []
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            # Skip ignored files and directories
            logging.debug(f"Checking {item_path}")
            if self.is_ignored(item_path, ignore_files):
                continue
            logging.info(f"Add to structure: {item_path}")

            if os.path.isdir(item_path):
                markdown_lines.append(f"{'  ' * indent_level}- **{item}/**")
                markdown_lines.extend(self.generate_project_structure(item_path, indent_level + 1, ignore_files))
            else:
                markdown_lines.append(f"{'  ' * indent_level}- {item}")
        return markdown_lines

    def generate_environment_requirements(self):
        logging.info("Generating environment requirements...")
        logging.warning("Please ensure that the environment requirements are accurate and up-to-date!")
        os.system(f"pip freeze > {os.path.join(self.out_put_dir, 'requirements_env.txt')}")
        logging.info(
            f"Environment requirements have been saved to {os.path.join(self.out_put_dir, 'requirements_env.txt')}")
        requirements_env = []
        with open(os.path.join(self.out_put_dir, 'requirements_env.txt'), 'r') as f:
            for line in f:
                requirements_env.append(line.strip())
        logging.debug(requirements_env)
        return requirements_env

    def find_imports(self, content):
        import_code_lines = []
        for line in content.split("\n"):
            if line.startswith("import") or line.startswith("from"):
                import_code_lines.append(line)
        return import_code_lines

    def generate_project_requirements(self):
        def parse_requirements_output(output):
            logging.debug("Parsing requirements output")
            try:
                # "```json {\"requirements\": [\"module1==1.0.0\", \"module2==2.0.0\"]} ```"
                # remove the leading and trailing "```json" and "```"
                output_str = output.lstrip("```json").rstrip("```")
                output_dict = json.loads(output_str)
                output_list = output_dict["requirements"]
            except Exception as e:
                logging.error(f"Error parsing requirements output: {output}, {e}")
                output_list = []
            logging.debug(output_list)
            return output_list

        environment_requirements = self.generate_environment_requirements()
        environment_requirements_str = "\n".join(environment_requirements)
        logging.info("Generating project requirements...")
        scripts = self.find_all_scripts_and_config_files()
        import_code_lines = []
        for script in scripts:
            logging.debug(f"Reading script: {script}")
            with open(script, "r") as f:
                content = f.read()
            import_code_lines.extend(self.find_imports(content))
        import_code_lines_str = "\n".join(import_code_lines)
        sys_instruction = (
            "Based on the following Python code and the existing environment-exported `requirements.txt`, generate a new `requirements.txt` file. "
            "Ensure that the final file accurately reflects the modules used in the code, removing any unnecessary dependencies and including the correct versions.\n"
            "```python\n"
            f"{import_code_lines_str}\n"
            "```\n"
            "Existing `requirements.txt` content:\n"
            "```\n"
            f"{environment_requirements_str}\n"
            "```\n"
            "The output should be a markdown code snippet formatted in JSON, such as: "
            "```json {\"requirements\": [\"module1==1.0.0\", \"module2==2.0.0\"]} ```"
        )
        prompt = [{"role": "system", "content": sys_instruction}]
        logging.debug(f'prompt: {prompt}')
        answer = get_model_answer(model_name=self.model, inputs_list=prompt, config_dir=self.config_dir)
        requirements_list = parse_requirements_output(answer)
        return requirements_list

    def generate_file_description(self, script_path):
        with open(script_path, "r") as f:
            script_content = f.read()
        sys_instruction = (
            'Please generate a summarized description that outlines the functionality of the following code/script,'
            ' including its input and output parameters, key algorithms or logic.'
            ' Ensure the description is clear and concise, suitable for technical documentation or code comments.'
        )
        if self.language == "cn":
            sys_instruction += "用中文回答。"
        prompt = [{"role": "system", "content": sys_instruction}, {"role": "user", "content": script_content}]
        logging.debug(f'prompt: {prompt}')
        answer = get_model_answer(model_name=self.model, inputs_list=prompt, config_dir=self.config_dir)
        logging.debug(f'***** description of {script_path} *****')
        logging.debug(f'{answer}')
        logging.debug(f'*****')
        return answer

    def get_dependency_content(self):
        logging.info("Reading dependency content")
        files = os.listdir(self.out_put_dir)
        if files == []:
            return {}
        dependency_content = {}
        for file in files:
            if file == "requirements.txt" or file == "PROJECT_STRUCTURE.md" or file == "SCRIPT_DESCRIPTION.json" or "README" in file:
                with open(os.path.join(self.out_put_dir, file), "r") as f:
                    content = f.read()
                dependency_content[file.title()] = content
        logging.debug(dependency_content)
        return dependency_content

    def generate_readme(self):
        sys_instruction = (
            "Generate a comprehensive README file for this project that includes, but is not limited to the following sections. If specific details are unknown, set <> as placeholders: "
            "1. Project Title: The name of the project."
            "2. Description: A brief overview of the project's purpose, features, and key functionalities."
            "3. Configuration: Information on any configuration files or environment variables required."
            "4. Installation: Step-by-step instructions on how to install and set up the project, including any dependencies."
            "5. Usage: Examples of how to use the project, including any command-line instructions or code snippets. Indicates main function or entry of the program."
            "6. Output: The expected output position and data formats of the output."
            "7. Contact Information: How to reach the maintainers or developers for support or inquiries."
            "Ensure that the README is clear, well-organized, and helpful for both new users and contributors."
        )
        if self.language == "cn":
            sys_instruction += "用中文回答。"
        dependencies = self.get_dependency_content()
        if dependencies == {}:
            logging.error("No dependency files found. Please run 'generate_dependency' first.")
            return
        query = (
            'The information of this project is as follows:\n'
            f'project_name: {self.project_name}\n'
            f'project_author: {self.project_author}\n'
            f'project_author_info: {self.project_author_info}\n'
            f'project_short_description: {self.project_description}\n'
        )
        for title, content in dependencies.items():
            query += f"\n\n{title}:\n{content}"
        prompt = [{"role": "system", "content": sys_instruction}, {"role": "user", "content": query}]
        logging.debug(f'prompt: {prompt}')
        answer = get_model_answer(model_name=self.model, inputs_list=prompt, config_dir=self.config_dir)
        logging.debug(f'***** README *****')
        logging.debug(f'{answer}')
        logging.debug(f'*****')
        save_content_to_file(answer, self.readme_path)
        logging.info(f"README has been generated and saved to {self.readme_path}")


def save_content_to_file(content, file_path):
    with open(file_path, "w", encoding='utf-8') as f:
        f.write(content)
        logging.info(f"Saved to {file_path}")


def sample():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    # Initialize AutoReadme
    project_name = "AutoReadme"
    project_dir = os.path.join(ROOT_DIR)
    author = "Lintao:lint22@mails.tsinghua.edu.cn"
    model_name = "gpt-4o"
    project_description = "AutoReadme is a tool that automatically generates README files and dependencies for a given project directory."
    auto_readme = AutoReadme(
        project_name=project_name,
        project_dir=project_dir,
        author=author,
        model_name=model_name,
        project_description=project_description,
    )
    # auto_readme.generate_project_requirements()
    auto_readme.generate_dependency()
    auto_readme.generate_readme()


if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Generate README and dependencies using AutoReadme.")

    # Required arguments with default values
    parser.add_argument('--project_name', type=str, help="Name of the project.")
    parser.add_argument('--project_dir', type=str, help="Directory of the project.")
    parser.add_argument('--author', type=str, help="Author of the project.")
    parser.add_argument('--author_info', type=str,
                        help="Author's information of the project, including name, email, phone number, etc.")

    # Optional arguments with defaults set to None
    parser.add_argument('--model_name', type=str, default=None, help="Model name for AutoReadme.")
    parser.add_argument('--out_put_dir', type=str, default=None, help="Directory for dependencies.")
    parser.add_argument('--project_description', type=str, default=None, help="Description of the project.")
    parser.add_argument('--config_dir', type=str, default=None, help="Directory for configuration files.")

    # New optional 'language' argument
    parser.add_argument('--language', type=str, choices=['cn', 'en'], default='en',
                        help="Language for the project. Options: 'cn' or 'en'. Default is 'en'.")

    # Parse the arguments
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Initialize AutoReadme with the provided arguments
    auto_readme = AutoReadme(
        project_name=args.project_name,
        project_dir=args.project_dir,
        author=args.author,
        author_info=args.author_info,
        model_name=args.model_name,
        out_put_dir=args.out_put_dir,
        project_description=args.project_description,
        config_dir=args.config_dir,
        language=args.language
    )

    # Generate dependency and README files
    auto_readme.generate_dependency()
    auto_readme.generate_readme()
