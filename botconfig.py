PASS = "" # NS pass
CHANNEL = ""
HOST = "irc.esper.net"
PORT = +6697
USERNAME = ""  # for authentication, can be left blank if same as NICK
NICK = ""
CMD_CHAR = "!"
CHANGING_HOST_QUIT_MESSAGE = "Changing host"
ADMIN_CHAN = "" # logging chan. leave blank to disable logging
ALT_CHANS = "" # will join all of these channels upon connect if RAW_JOIN in .\settings\wolfgame.py is set to True
DEV_CHAN = "" # development chan. bot will automatically fetch updates whenever the GitHub bot joins and tells as such. ALLOW_GIT in .\settings\wolfgame.py must be True
DEV_BOT = "" # github bot's nickname, to which it will check for updates
PROJECT_NAME = "" # GitHub project name, owned by GIT_OWNER
BRANCH_NAME = "master" # GitHub branch  to look for updates
GIT_OWNER  "" # Who pushes commits to master
SPECIAL_CHAN = "" # special channel for various purposes. leave blank if you don't want the bot to join it
PERFORM = "" # commands to perform on connect. do NOT put a / or it will not work. syntax: "COMMAND param1 param2 :data to send"
COMMON_HOSTS = ("", "") # hosts that more than one person use; ident@host will be used instead
DISABLED_COMMANDS = ["roles"] # disabled commands. at least must be specified, blank if needed

SASL_AUTHENTICATION = True  # put account name in USERNAME ^ if different from nick
USE_SSL = True
DISABLE_DEBUG_MODE = False  # Entirely disable debug mode
IGNORE_HIDDEN_COMMANDS = True # Ignore commands sent to @#channel or +#channel
ALLOW_NOTICE_COMMANDS = False  # allow /notice #channel !command to be interpreted as a command
ALLOW_PRIVATE_NOTICE_COMMANDS = False  # allow !command's from /notice (Private)
PING_NOTICE = True # sends a /notice to the whole channel when !ping is used, instead of a msg
REVERSE_PING = True # needs users to send !in and !out to be pinged or not if set to True
OP_NEEDED = True # defines if the +o status is needed for the bot to work

ALLOWED_NORMAL_MODE_COMMANDS = ["eval", "revealroles", "exec"]  # debug mode commands to be allowed in normal mode

OWNERS = ("207.253.26.192", "ip72-218-84-12.hr.hr.cox.net", "chaos.esper.net")  # the comma is required at the end if there is one owner
ADMINS = ("c-76-16-239-79.hsd1.in.comcast.net", "rrcs-67-53-188-198.west.biz.rr.com", "pool-173-74-63-12.dllstx.fios.verizon.net")  # glob syntax supported (wildcards)
OWNERS_ACCOUNTS = ("Vgr255", "R2D2Warrior", "Raiden", "Steve_Restless", "benhunter09", "geraldbrent") # same as OWNERS, except with accounts
ADMINS_ACCOUNTS = ("Soul", "stiva", "TheBadShepperd") # I'd rather not use wildcards
ALLOW = {"none": ("fwait",),         # will only work by cloak
         "none": ("fday","fnight")}
DENY = {}

# Stop editing here

# Argument --debug means start in debug mode
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true')
parser.add_argument('--sabotage', action='store_true')

args = parser.parse_args()
DEBUG_MODE = args.debug if not DISABLE_DEBUG_MODE else False

DEFAULT_MODULE = "sabotage" if args.sabotage else "wolfgame"
