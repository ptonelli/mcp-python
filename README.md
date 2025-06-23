# Rationale

I want my LLM to be able to read, modify and update my code. this implies it
should be able to:

- read and write files and directories
- run code (at least python)
- install dependencies (uv or venv)

Now on how I want to do it: This should run on its own : no need for an
additional machine or API access. The LLM must not have the ability to run
containers. The setup must itself be running inside a container with a mounting
point for data to easily run on a home server.

# Organisation

3 sets of tools

- file management
- git management
- code execution

# Python execution (WIP)

No complex security, the python code must run and the LLM must be able to add its own deps to run the code.

# File management (WIP)

The data must be in a volume mounted in the docker. One directory per project +
the ability to have nested projects for more complex setups.

No overly complex security, rely on backups of the volume if necessary

# Git management (TODO)

Simple access to git repos, the keys should not be available to the LLM.
