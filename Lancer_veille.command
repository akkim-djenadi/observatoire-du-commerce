#!/bin/bash
# Double-cliquer sur ce fichier pour ouvrir le tableau de bord dans le navigateur.
cd "$(dirname "$0")" || exit 1
python3 -m streamlit run app.py --server.headless false
