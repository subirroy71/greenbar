# A real animated GIF of the Greenbar CLI, for use as a NotebookLM video source.
# Needs charmbracelet/vhs:  brew install vhs   (or see https://github.com/charmbracelet/vhs)
# Render from the repo root:  vhs scripts/notebooklm/demo.tape  ->  build/notebooklm/greenbar-demo.gif

Output build/notebooklm/greenbar-demo.gif
Set FontSize 20
Set Width 1200
Set Height 720
Set Padding 20
Set Theme "Dracula"

Type "greenbar lint contracts/CONTRACT.md"        Enter   Sleep 2s
Type "greenbar orient --path src/greenbar --budget 300"    Enter   Sleep 2500ms
Type "greenbar gate scoped --contract contracts/CONTRACT.md"      Enter   Sleep 3s
Type "greenbar report"                            Enter   Sleep 2s
Sleep 2s
