## Wolfbot


**Use Python 3.2 (3.1 doesn't work)**

### Running

1. Install Python (min. 3.2)
2. Copy `botconfig.py.example` to `botconfig.py` and modify to your heart's content.
3. If desired, configure `settings/wolfgame.py` to modify game settings.
4. Run the bot: `python wolfbot.py`

### Auto-Update / Git Integration

If looking to use the auto-update feature, you need the Git shell.

* On Windows, you can download the Git shell at http://git-scm.com/download/win
* On Ubuntu/Debian systems, `apt-get install git` then `git clone http://github.com/Vgr255/Wolfbot.git`
* Mac users should install Homebrew, then can use `brew install git` in a terminal.

You don't need to do `git pull` as the bot will do that as long as git is installed.

You can clone the repository, or fork it. The IRC service needs to be enabled.

Whenever GitHub's commit IRC bot joins and says there's an update, it downloads it, provided ALLOW_GIT is set to True in `.\settings\wolfgame.py`
