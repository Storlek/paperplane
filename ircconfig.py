# Multiple servers "should" work but actually totally don't.
# port, username, password, and channels are optional
# username will use defaults if not defined here
servers = [
    dict(
        network='FreeNode',
        server='chat.freenode.net',
        #port=6665,
        #password='SuperSecretPassword',
        #username='somethingElse',
        #channels=['#here', '#there', '#anywhere'],
    ),
]

username = ''
nicknames = [username, username + '_', username + '`', username + '|']
realname = 'Flying on a paperplane!'

highlight = nicknames + [
    #'any', 'stuff', 'you', 'want', 'highlighted',
]

quit_message = "Oh, so THAT's what that button does."

font = 'sans 9'
bold_font = 'sans 9 bold'
colors = [
    '#ffffff', #  0 white
    '#000000', #  1 black
    '#000088', #  2 navy
    '#008800', #  3 green
    '#ff0000', #  4 bright red
    '#880000', #  5 dark red
    '#880088', #  6 violet
    '#ff8800', #  7 orange
    '#ffff00', #  8 yellow
    '#00ff00', #  9 lime
    '#008888', # 10 teal
    '#00ffff', # 11 cyan
    '#0000ff', # 12 bright blue
    '#ff00ff', # 13 magenta
    '#888888', # 14 dark grey
    '#cccccc', # 15 light grey
]
nickcolors = [2, 3, 4, 5, 6, 7, 9, 10, 12, 13]

cmd_prefix = '/'
hush_motd = True # skip the motd on startup
strip_control = False # hide colors, etc.

time_format = '[%H:%M] '
time_offset = None

# widthxheight+top+left
# widthxheight-bottom-right
# widthxheight
geometry = '600x400'
