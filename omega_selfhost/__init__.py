"""Self-hosted Omega compiler and native tensor toolchain.

The Python modules only bootstrap or invoke native tools and render proof data.
The production lexer, parser, shape checker, optimizer and emitter live in
compiler.omega and run as native executables after bootstrap.
"""
