# A real animated GIF of the Trellis CLI, for use as a NotebookLM video source.
# Needs charmbracelet/vhs:  brew install vhs   (or see https://github.com/charmbracelet/vhs)
# Render from the repo root:  vhs scripts/notebooklm/demo.tape  ->  build/notebooklm/trellis-demo.gif

Output build/notebooklm/trellis-demo.gif
Set FontSize 20
Set Width 1200
Set Height 720
Set Padding 20
Set Theme "Dracula"

Type "trellis lint contracts/CONTRACT.md"        Enter   Sleep 2s
Type "trellis orient --path src/trellis --budget 300"    Enter   Sleep 2500ms
Type "trellis gate scoped --contract contracts/CONTRACT.md"      Enter   Sleep 3s
Type "trellis report"                            Enter   Sleep 2s
Sleep 2s
