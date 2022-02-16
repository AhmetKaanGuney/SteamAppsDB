"""Download and save non_game_apps and failed_requests"""

try:
    from update import fetch
except:
    from .update import fetch

# Dirs
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)

NON_GAME_APPS_API = "localhost:500/GetApp"

def main():
    print("===           Download to DB          ===")
    pass
