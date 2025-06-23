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

2 sets of tools

- shell prompt
- code execution

# Shell prompt (WIP)

Just provide a shell prompt with the ability to set the current active directory.

# Python execution (WIP)

No complex security, the python code must run and the LLM must be able to add its own deps to run the code.
