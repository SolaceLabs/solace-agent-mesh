# Copy custom git hooks to the .git/hooks directory
cp -r .githooks/* .git/hooks/
# Ensure the hooks are executable
chmod -R +x .git/hooks/*