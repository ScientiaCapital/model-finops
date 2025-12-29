#!/bin/bash
echo "=== Railway Login ==="
echo "Please authenticate in your browser..."
echo ""
railway login
echo ""
echo "Verifying authentication..."
railway whoami
echo ""
echo "Done! You can close this window."
