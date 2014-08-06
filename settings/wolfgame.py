import botconfig
                             #####################################################################################
PING_WAIT = 300              # seconds                                                                           #
PING_MIN_WAIT = 30           # amount of time between first !join and !ping can be allowed                       #
MINIMUM_WAIT = 60            # amount of time the players must wait between the first !join and !start           #
EXTRA_WAIT = 20              # amount of time !wait adds before starting the game                                #
EXTRA_WAIT_JOIN = 0          # Add this many seconds to the waiting time for each !join (unusued yet)            #
WAIT_AFTER_JOIN = 10         # Wait at least this many seconds after the last join (still yet to implement)      #
MAXIMUM_WAITED = 3           # limit for amount of !wait's                                                       #
STATS_RATE_LIMIT = 15        # time between two !stats                                                           #
VOTES_RATE_LIMIT = 15        # time between two !votes                                                           #
ADMINS_RATE_LIMIT = 300      # time between two !admins                                                          #
GSTATS_RATE_LIMIT = 0        # time to wait for each !gamestats                                                  #
PSTATS_RATE_LIMIT = 0        # time to wait for each !player                                                     #
TIME_RATE_LIMIT = 30         # time to wait for each !time                                                       #
SHOTS_MULTIPLIER = .16       # ceil(shots_multiplier * len_players) = bullets given                              #
MOLOTOV_AMOUNT = .11         # ceil(molotov_ammount * len_players) = molotovs given                              #
MIN_PLAYERS = 4              # minimum amount of players needed to start a game                                  #
MAX_PLAYERS = 30             # maximum amount of players allowed                                                 #
DRUNK_SHOTS_MULTIPLIER = 3   # drunk gets more bullets                                                           #
DRUNK_FIRE_MULTIPLIER = 5    # drunk gets way more molotovs. but he can die as easily                            #
NIGHT_TIME_WARN = 90         # should be less than NIGHT_TIME_LIMIT                                              #
NIGHT_TIME_LIMIT = 120       # night ends after x seconds (default is 120)                                       #
DAY_TIME_LIMIT_WARN = 480    # warns before the day changes                                                      #
DAY_TIME_LIMIT_CHANGE = 120  # seconds after DAY_TIME_LIMIT_WARN has passed                                      #
JOIN_TIME_LIMIT = 1800       # amount of time (in seconds) before game is cancelled after first join             #
SHORT_DAY_PLAYERS = 6        # Number of players left to have a short day                                        #
SHORT_DAY_LIMIT_WARN = 180   # same as above, except for small days. only set if above is also set               #
SHORT_DAY_LIMIT_CHANGE = 120 # same as above, except for small days                                              #
START_WITH_DAY = False       # obviously, does game starts with day?                                             #
WOLF_STEALS_GUN = True       # if True, gun will be handed to a random wolf/traitor/werecrow when gunner dies    #
WOLF_STEALS_FIRE = True      # same, but for the arsonist instead                                                #
KILL_IDLE_TIME = 300         # amount of seconds before the player is removed from the game                      #
WARN_IDLE_TIME = 180         # warns after x seconds, before the player is removed from the game                 #
PART_GRACE_TIME = 30         # amount of seconds the bot waits before removing when user /parts                  #
QUIT_GRACE_TIME = 30         # amount of seconds the bot waits before removing when user /quits                  #
MIN_LOG_PLAYERS = 12         # number of players needed to disable logging (reducing lag)                        #
MAX_PRIVMSG_TARGETS = 1      # better not touch that...                                                          #
LEAVE_STASIS_PENALTY = 0     # number of games user is not allowed to join if they !leave                        #
IDLE_STASIS_PENALTY = 0      # same, if they idle out                                                            #
PART_STASIS_PENALTY = 0      # same but for /part instead                                                        #
SELF_LYNCH_ALLOWED = True    # can you lynch yourself?                                                           #
GOAT_HERDER = True           # new role? not sure                                                                #
HIDDEN_TRAITOR = True        # something about hiding the traitor, making it look like a villager?               #
CANT_KILL_TRAITOR = True     # Can the wolves kill the traitor?                                                  #
CARE_BOLD = False            # determines if the bot cares about bolds in channel                                #
CARE_COLOR = False           # same, except for color                                                            #
KILL_COLOR = False           # does the bot kick you for using color                                             #
KILL_BOLD = False            # same, but for bold                                                                #
CARE_ADVERTISING = False     # warns any message containing a '#' in it (advertising, hashtag, etc)              #
KILL_ADVERTISING = False     # kicks on advertising                                                              #
EXEMPT_ADMINS = True         # doesn't kick admins/owners                                                        #
BAN_AFTER_KICKS = True       # decide whether user will be banned/quieted after being kicked                     #
TIME_BEFORE_UNSET = 30       # amount of time (in seconds) before user is un-banned/quieted                      #
BAN_TYPE = "q"               # should be either q or b (WITHOUT the +) to decide between ban or quiet            #
AUTO_OP_FLAG = True          # used to decide whether the bot will send /msg ChanServ op on connect              #
AUTO_OP_FAIL = False         # if set to True it will send an error to the channel upon connecting               #
RAW_JOIN = True              # allow to join other chans than the default one                                    #
LOG_CHAN = False             # logs activity in botconfig.ADMIN_CHAN                                             #
LOG_AUTO_TOGGLE = True       # automatically disables logging if there are too many players                      #
AUTO_LOG_TOGGLE = False      # automatically toggle logging when an admin gets in the admin_chan                 #
MINIMALIST_LOG = True        # only displays sensible commands. only useful if LOG_CHAN = False                  #
EXT_PING = ""                # external pinging in the special channel. leave blank to disable it                #
MAX_ERRORS = 4               # max amount of errors that can happen before the bot quits                         #
USE_IDENT = False            # defines if should use ident along with host for !ping and similar                 #
ALLOW_GIT = True             # joins the development channel and automatically fetches commits                   #
AUTO_OP_DEOP = True          # determines if bot ops and deops chanops on start and endgame                      #
                             #####################################################################################
LOG_FILENAME = ""
BARE_LOG_FILENAME = ""

                    #       HIT    MISS    SUICIDE
GUN_CHANCES         =   (   5/7  ,  1/7  ,   1/7   )
DRUNK_GUN_CHANCES   =   (   3/7  ,  3/7  ,   1/7   )
MANSLAUGHTER_CHANCE =       1/5  # ACCIDENTAL HEADSHOT (FATAL)

                    #    SUCCESS   MISS    SUICIDE
FIRE_CHANCES        =   (   3/7  ,  3/7  ,   1/7   )
DRUNK_FIRE_CHANCES  =   (   2/7  ,  2/7  ,   3/7   )

GUNNER_KILLS_WOLF_AT_NIGHT_CHANCE = 7/10
PYRO_KILLS_WOLF_AT_NIGHT_CHANCE = 4/5
GUARDIAN_ANGEL_DIES_CHANCE = 1/2
DETECTIVE_REVEALED_CHANCE = 2/5

#########################################################################################################################
#   ROLE INDEX:   PLAYERS   SEER    WOLF   CURSED   DRUNK   HARLOT  TRAITOR  GUNNER   CROW    ANGEL DETECTIVE  PYRO    ##
#########################################################################################################################
ROLES_GUIDE = {    4    : (   0   ,   1   ,   0   ,   0   ,   0   ,    0   ,   0   ,   0    ,   0   ,   0   ,   0   ), ##
                   5    : (   1   ,   1   ,   0   ,   0   ,   0   ,    0   ,   0   ,   0    ,   0   ,   0   ,   0   ), ##
                   6    : (   1   ,   1   ,   1   ,   1   ,   0   ,    0   ,   0   ,   0    ,   0   ,   0   ,   0   ), ##
                   7    : (   1   ,   1   ,   1   ,   1   ,   0   ,    0   ,   0   ,   0    ,   0   ,   0   ,   0   ), ##
                   8    : (   1   ,   2   ,   1   ,   1   ,   1   ,    0   ,   0   ,   0    ,   0   ,   0   ,   0   ), ##
                   9    : (   1   ,   2   ,   1   ,   1   ,   1   ,    0   ,   0   ,   0    ,   0   ,   0   ,   0   ), ##
                   10   : (   1   ,   2   ,   1   ,   1   ,   1   ,    1   ,   1   ,   0    ,   0   ,   0   ,   0   ), ##
                   11   : (   1   ,   2   ,   1   ,   1   ,   1   ,    1   ,   1   ,   0    ,   0   ,   0   ,   0   ), ##
                   12   : (   1   ,   2   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   0   ,   0   ), ##
                   13   : (   1   ,   2   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   0   ,   0   ), ##
                   14   : (   1   ,   2   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   15   : (   1   ,   2   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   16   : (   1   ,   2   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   17   : (   1   ,   2   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   18   : (   1   ,   3   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   19   : (   1   ,   3   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   20   : (   1   ,   3   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   21   : (   2   ,   4   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   22   : (   2   ,   4   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   23   : (   2   ,   4   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   24   : (   2   ,   4   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   25   : (   2   ,   4   ,   1   ,   1   ,   1   ,    1   ,   1   ,   1    ,   1   ,   1   ,   0   ), ##
                   26   : (   2   ,   5   ,   1   ,   1   ,   1   ,    1   ,   2   ,   1    ,   1   ,   1   ,   0   ), ##
                   27   : (   2   ,   5   ,   1   ,   1   ,   1   ,    1   ,   2   ,   1    ,   1   ,   1   ,   0   ), ##
                   28   : (   2   ,   5   ,   1   ,   1   ,   1   ,    1   ,   2   ,   1    ,   1   ,   1   ,   0   ), ##
                   29   : (   2   ,   5   ,   1   ,   1   ,   1   ,    1   ,   2   ,   1    ,   1   ,   1   ,   0   ), ##
                   30   : (   2   ,   5   ,   1   ,   1   ,   1   ,    1   ,   2   ,   1    ,   1   ,   1   ,   0   ), ##
                   None : (   0   ,   0   ,   0   ,   0   ,   0   ,    0   ,   0   ,   0    ,   0   ,   0   ,   0   )} ##
#########################################################################################################################
#   Notes:  It is not needed to have a line for every combination, but it helps when you want to tweak a bit           ##
#   Notes:  If one line is not specified (aka left out, doesn't appear) it will consider the next lower one            ##
#########################################################################################################################


GAME_MODES = {}
AWAY = []  # cloaks of people who are away.
PING_IN = []  # cloaks of people who used !in to get in the ping list. works only with botconfig.REVERSE_PING set to True
SIMPLE_NOTIFY = []  # cloaks of people who !simple, who want everything /notice'd

ROLE_INDICES = {0 : "seer",
                1 : "wolf",
                2 : "cursed villager",
                3 : "village drunk",
                4 : "harlot",
                5 : "traitor",
                6 : "gunner",
                7 : "werecrow",
                8 : "guardian angel",
                9 : "detective",
                10: "arsonist"}
                
INDEX_OF_ROLE = dict((v,k) for k,v in ROLE_INDICES.items())


NO_VICTIMS_MESSAGES = ("The body of a young penguin pet is found.",
                       "A pool of blood and wolf paw prints are found.",
                       "Traces of wolf fur are found.")
LYNCH_MESSAGES = ("The villagers, after much debate, finally decide on lynching \u0002{0}\u0002, who turned out to be... a \u0002{1}\u0002.",
                  "Under a lot of noise, the pitchfork-bearing villagers lynch \u0002{0}\u0002, who turned out to be... a \u0002{1}\u0002.",
                  "The villagers drag the poor \u0002{0}\u0002 to the tree on the edge of the village. The poor guy was... a \u0002{1}\u0002.",
                  "The mob drags a protesting \u0002{0}\u0002 to the hanging tree. S/He succumbs to the will of the horde, and is hanged. It is discovered (s)he was a \u0002{1}\u0002.",
                  "Resigned to his/her fate, \u0002{0}\u0002 is led to the gallows. After death, it is discovered (s)he was a \u0002{1}\u0002.")
RULES = (botconfig.CHANNEL + " channel rules:\n"+
                             "1) Do not share information after death. "+
                             "2) Do not play with bots or clones. "+
                             "3) Do not quit unless you need to leave. "+
                             "4) Do not paste messages from the bot during the game. "+
                             "5) Do not ping people unless they have played recently.\n"+
                             "6) Do not advertise another channel or network. "+
                             "7) Do not take advantage of a player timing out. "+
                             "8) Using anti-idle messages or /whois idle times \u0002IS\u0002 cheating. "+
                             "9) If you are unsure whether you can do something or not, ask an operator. "+
                             "10) Channel and bot operators have the final word.")
         

is_role = lambda plyr, rol: rol in ROLES and plyr in ROLES[rol]

def plural(role):
    if role == "wolf": return "wolves"
    elif role == "person": return "people"
    else: return role + "s"
    
def list_players():
    pl = []
    burnt = []
    for burned in BURNED: # burned players' roles still appear, but they mustn't be marked as alive
        burnt.append(burned)
    for x in ROLES.values():
        if x in burnt:
            continue
        pl.extend(x)
    return pl
    
def list_players_and_roles():
    plr = {}
    for x in ROLES.keys():
        for p in ROLES[x]:
            plr[p] = x
    return plr

def get_reveal_role(nick):
    if HIDDEN_TRAITOR and get_role(nick) == "traitor":
        return "villager"
    else:
        return get_role(nick)
    
get_role = lambda plyr: list_players_and_roles()[plyr]


def del_player(pname):
    prole = get_role(pname)
    ROLES[prole].remove(pname)
    

    
class InvalidModeException(Exception): pass
def game_mode(name):
    def decor(c):
        GAME_MODES[name] = c
        return c
    return decor

    
CHANGEABLE_ROLES = { "seers"  : INDEX_OF_ROLE["seer"],
                     "wolves" : INDEX_OF_ROLE["wolf"],
                     "cursed" : INDEX_OF_ROLE["cursed villager"],
                    "drunks"  : INDEX_OF_ROLE["village drunk"],
                   "harlots"  : INDEX_OF_ROLE["harlot"],
                   "traitors" : INDEX_OF_ROLE["traitor"],
                   "gunners"  : INDEX_OF_ROLE["gunner"],
                 "werecrows"  : INDEX_OF_ROLE["werecrow"],
                 "angels"     : INDEX_OF_ROLE["guardian angel"],
                 "detectives" : INDEX_OF_ROLE["detective"],
                 "arsonists"  : INDEX_OF_ROLE["arsonist"]}
    



# TODO: implement game modes
@game_mode("roles")
class ChangedRolesMode(object):
    """Example: !fgame roles=wolves:1,seers:0,angels:1"""
    
    def __init__(self, arg):
        self.ROLES_GUIDE = ROLES_GUIDE.copy()
        lx = list(ROLES_GUIDE[None])
        pairs = arg.split(",")
        pl = list_players()
        if not pairs:
            raise InvalidModeException("Invalid syntax for mode roles.")
        for pair in pairs:
            change = pair.split(":")
            if len(change) != 2:
                raise InvalidModeException("Invalid syntax for mode roles.")
            role, num = change
            try:
                num = int(num)
                try:
                    lx[CHANGEABLE_ROLES[role.lower()]] = num
                except KeyError:
                    raise InvalidModeException(("The role \u0002{0}\u0002 "+
                                                "is not valid.").format(role))
            except ValueError:
                raise InvalidModeException("A bad value was used in mode roles.")
        for k in ROLES_GUIDE.keys():
            self.ROLES_GUIDE[k] = tuple(lx)

         
# Persistence
         
         
# Load saved settings
import sqlite3
import os

conn = sqlite3.connect("data.sqlite3", check_same_thread = False)

with conn:
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS away (nick TEXT)')  # whoops, i mean cloak, not nick

    c.execute('CREATE TABLE IF NOT EXISTS simple_role_notify (cloak TEXT)') # people who understand each role

    c.execute('SELECT * FROM away')
    for row in c:
        AWAY.append(row[0])

    c.execute('SELECT * FROM simple_role_notify')
    for row in c:
        SIMPLE_NOTIFY.append(row[0])

    # populate the roles table
    c.execute('DROP TABLE IF EXISTS roles')
    c.execute('CREATE TABLE roles (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT)')

    for x in ["villager"]+list(ROLE_INDICES.values()):
        c.execute("INSERT OR REPLACE INTO roles (role) VALUES (?)", (x,))


    c.execute(('CREATE TABLE IF NOT EXISTS rolestats (player TEXT, role TEXT, '+
        'teamwins SMALLINT, individualwins SMALLINT, totalgames SMALLINT, '+
        'UNIQUE(player, role))'))

        
    c.execute(('CREATE TABLE IF NOT EXISTS gamestats (size SMALLINT, villagewins SMALLINT, ' +
        'wolfwins SMALLINT, totalgames SMALLINT, UNIQUE(size))'))
        


    
    
#def remove_away(clk):
#    with conn:
#        c.execute('DELETE from away where nick=?', (clk,))
    
#def add_away(clk):
#    with conn:
#        c.execute('INSERT into away VALUES (?)', (clk,))

#def add_ping(clk):
#    with conn:
#        c.execute('INSERT into ping VALUES (?)', (clk,))
        
#def remove_ping(clk):
#    with conn:
#        c.execute('DELETE from ping where nick=?', (clk,))
        
#def remove_simple_rolemsg(clk):
#    with conn:
#        c.execute('DELETE from simple_role_notify where cloak=?', (clk,))
    
#def add_simple_rolemsg(clk):
#    with conn:
#        c.execute('INSERT into simple_role_notify VALUES (?)', (clk,))
        
        

def update_role_stats(acc, role, won, iwon):
    with conn:
        wins, iwins, total = 0, 0, 0

        c.execute(("SELECT teamwins, individualwins, totalgames FROM rolestats "+
                   "WHERE player=? AND role=?"), (acc, role))
        row = c.fetchone()
        if row:
            wins, iwins, total = row

        if won:
            wins += 1
        if iwon:
            iwins += 1
        total += 1

        c.execute("INSERT OR REPLACE INTO rolestats VALUES (?,?,?,?,?)",
                  (acc, role, wins, iwins, total))

def update_game_stats(size, winner):
    with conn:
        vwins, wwins, total = 0, 0, 0
        
        c.execute("SELECT villagewins, wolfwins, totalgames FROM gamestats "+
                   "WHERE size=?", (size,))
        row = c.fetchone()
        if row:
            vwins, wwins, total = row
        
        if winner == "wolves":
            wwins += 1
        elif winner == "villagers":
            vwins += 1
        total += 1
        
        c.execute("INSERT OR REPLACE INTO gamestats VALUES (?,?,?,?)",
                    (size, vwins, wwins, total))
        
def get_player_stats(acc, role):
    if role.lower() not in ["villager"] + [v.lower() for k, v in ROLE_INDICES.items()]:
        return "No such role: {0}".format(role)
    with conn:
        c.execute("SELECT player FROM rolestats WHERE player=? COLLATE NOCASE", (acc,))
        player = c.fetchone()
        if player:
            for row in c.execute("SELECT * FROM rolestats WHERE player=? COLLATE NOCASE AND role=? COLLATE NOCASE", (acc, role)):
                msg = "\u0002{0}\u0002 as \u0002{1}\u0002 | Team wins: {2} (%d%%), Individual wins: {3} (%d%%), Total games: {4}".format(*row)
                return msg % (round(row[2]/row[4] * 100), round(row[3]/row[4] * 100))
            else:
                return "No stats for {0} as {1}.".format(player[0], role)
        return "{0} has not played any games.".format(acc)

def get_player_totals(acc):
    role_totals = []
    with conn:
        c.execute("SELECT player FROM rolestats WHERE player=? COLLATE NOCASE", (acc,))
        player = c.fetchone()
        if player:
            c.execute("SELECT role, totalgames FROM rolestats WHERE player=? COLLATE NOCASE", (acc,))
            rows = c.fetchall()
            total = 0
            for row in rows:
                total += row[1]
            for row in rows:
                role_totals.append("\u0002{row[0]}\u0002: {row[1]} ({prct:.2%})".format(row=row, prct=row[1]/total))
            return "\u0002{0}\u0002's totals | \u0002{1} total games\u0002 | {2}".format(player[0], total, ", ".join(role_totals))
        else:
            return "{0} has not played any games.".format(acc)
            
def get_game_stats(size):
    with conn:
        for row in c.execute("SELECT * FROM gamestats WHERE size=?", (size,)):
            msg = "\u0002{0}\u0002 player games | Village wins: {1} (%d%%),  Wolf wins: {2} (%d%%), Total games: {3}".format(*row)
            return msg % (round(row[1]/row[3] * 100), round(row[2]/row[3] * 100))
        else:
            return "No stats for \u0002{0}\u0002 player games.".format(size)

def get_game_totals():
    size_totals = []
    total = 0
    with conn:
        for size in range(MIN_PLAYERS, MAX_PLAYERS + 1):
            c.execute("SELECT size, totalgames FROM gamestats WHERE size=?", (size,))
            row = c.fetchone()
            if row:
                size_totals.append("\u0002{0}p\u0002: {1}".format(*row))
                total += row[1]
    
    if len(size_totals) == 0:
        return "No games have been played."
    else:
        return "Total games ({0}) | {1}".format(total, ", ".join(size_totals))
