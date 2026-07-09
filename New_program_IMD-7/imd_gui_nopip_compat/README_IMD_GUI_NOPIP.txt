IMD GUI no-pip compatibility files
=================================

This package lets New_program_IMD-7/main.py run when pip/pyserial/requests cannot be installed.
It adds local replacements next to main.py:

- serial/                  minimal pyserial-compatible Windows COM module
- requests.py              minimal requests.post wrapper using urllib

How to use:
1) Copy the contents of New_program_IMD-7 from this archive into your project folder:
   C:\Users\Пользователь\Desktop\Isskb_project\New_program_IMD-7

2) Run:
   cd C:\Users\Пользователь\Desktop\Isskb_project\New_program_IMD-7
   py main.py

Important:
- Do not run the built-in ISSKB IMD reader and this GUI at the same time on COM6.
- If the GUI should send data to ISSKB, set ISSKB config/imd.json enabled=false, start ISSKB, then start this GUI.
- If ISSKB reads IMD directly, keep this GUI closed.
