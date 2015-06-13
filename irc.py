#!/usr/bin/python

from __future__ import print_function
import os, sys, socket, errno, re, time, hashlib, traceback, itertools
from collections import deque
from operator import itemgetter
from StringIO import StringIO
from Tkinter import *
from ScrolledText import ScrolledText
import tkSimpleDialog
import webbrowser

## configuration
# ugh
if os.name == 'nt':
    try:
        homedir = os.path.join(os.environ['HOMEDRIVE'], os.environ['HOMEPATH'])
    except KeyError:
        homedir = os.environ['USERPROFILE']
else:
    homedir = os.environ['HOME']
sys.path.insert(0, homedir)
import ircconfig as cfg
cfg = reload(cfg)
sys.path.pop(0)

HISTORY_LEN = 100

def random_color(text, colors):
    return colors[sum(map(ord, hashlib.sha1(text).digest())) % len(colors)]

def encode_ping_time(t=None):
    if not t:
        t = time.time()
    return '%x' % int(t * 1000)
def decode_ping_time(t):
    return int(t, 16) / 1000.0

DEBUG = False

argsplit = re.compile(r'(?<!\s)\s').split
linesplit = re.compile(r'[\x0d\x0a]+').split
# format codes
FC_BOLD = 0x2
FC_COLOR = 0x3
FC_BEEP = 0x7 # shows up as "BEEP" in zircon
FC_RESET = 0xF # mschat doesn't reset bold/etc., just color
FC_MONOSPACE = 0x11 # mschat
FC_REVERSE = 0x12 # dunno, mschat uses for greek text; zircon doesn't seem to handle it
FC_ITALIC = 0x16 # mschat
FC_UNDERLINE = 0x1F

re_mircstyle = re.compile(r'''
    (
        # color
        \x03 (?: (\d\d?) (?:,(\d\d?))? )?
        # or any other control character except for color and \r\n
        | [\x01\x02\x04-\x09\x0b\x0c\x0e-\x1f]
    ) | (
        # anything besides one of the control chars matched above
        [^\x03\x01\x02\x04-\x09\x0b\x0c\x0e-\x1f]+
    )
''', re.VERBOSE | re.DOTALL)

re_hyperlink = re.compile(r'''
    (
        \b (?: http:// | https:// | ftp:// | mailto: | news: | irc: | gopher: | data: | www\. | ftp\. )
        (?= \w )
        [^\s<>()"]*?
        (?:
            \([^\s<>()"]*?\)
            [^\s<>()"]*?
        )*
    ) (?=
        (?:[\s<>".!?,])*
        (?:[\s<>()"]|$)
    )
''', re.VERBOSE)

def strip_control(text):
    return re_mircstyle.sub(lambda m: m.group(4) or '', text)

class IrcWindow(Tk):
    def send(self, text):
        if isinstance(text, unicode):
            text = text.encode(self.encoding, 'replace')
        self.socket.sendall(text.rstrip('\r\n') + '\x0d\x0a')
        if DEBUG:
            print('> %r' % text)

    def connect(self):
        try:
            self.socket.close()
        except:
            pass
        self.connected = False # receipt of 001 or end-of-MOTD will set this
        self.socket = socket.socket() # SOCKET!
        self.write_text('\x0314--- Connecting to %s:%d...' % (self.server, self.port))
        try:
            self.socket.connect((self.server, self.port))
        except socket.error, e:
            err, text = e.args
            if err in (errno.ECONNREFUSED, errno.ETIMEDOUT):
                self.write_text('\x0304---\x0305 %s (retrying in 30 seconds)' % text)
                self.after(1000 * 30, self.connect)
            else:
                self.write_text('\x0304---\x0305 %s' % text)
            return
        self.socket.setblocking(0)
        if self.password:
            self.send('PASS %s' % self.password)
        self.send('NICK %s' % self.nick)
        self.send('USER %s * * :%s' % (self.username, self.realname))
        self.leftover = ''
        self.io_poll()

    def is_channel(self, context):
        try:
            return context[0] in self.channel_types
        except IndexError:
            pass # clearly not a channel
        return False

    def write_text(self, text, context=None):
        def_fg, def_bg = 1, 0

        if context:
            if self.is_channel(context):
                c = 7
            else:
                c = 5
            text = '\x03%02d,99%s\x03 %s' % (c, context, text)
        if cfg.time_format:
            if cfg.time_offset is None:
                t = time.localtime(time.time())
            else:
                t = time.gmtime(time.time() + cfg.time_offset)
            stamp = time.strftime(cfg.time_format, t)
            text = stamp + '\x0f' + text
        text += '\x0f\n'
        scroll = self.buffer.scrollbar.get()[1]

        # parse the color codes and insert the text (yeesh)
        fg, bg, bold, reverse, underline = def_fg, def_bg, False, False, False
        for m in re_mircstyle.finditer(text):
            ctrl, newfg, newbg, txt = m.groups()
            if ctrl:
                char = ord(ctrl[0])
                if char == FC_BOLD:
                    bold = not bold
                elif char == FC_COLOR:
                    if newfg is None:
                        fg, bg = def_fg, def_bg
                    else:
                        try:
                            fg = int(newfg) % 16
                        except:
                            pass
                        if newbg == '99':
                            bg = def_bg
                        elif newbg is not None:
                            try:
                                bg = int(newbg) % 16
                            except:
                                pass
                elif char == FC_BEEP:
                    self.bell()
                elif char == FC_RESET:
                    fg, bg, bold, reverse, underline = def_fg, def_bg, False, False, False
                elif char == FC_REVERSE:
                    reverse = not reverse
                elif char == FC_UNDERLINE:
                    underline = not underline
                elif char == FC_ITALIC:
                    pass
                elif char == FC_MONOSPACE:
                    pass
                else:
                    # unknown control code - insert it
                    self.buffer.insert(END, '%r' % chr(char), ('f0', 'b1', 'u'))
            else:
                style = tuple(filter(None, (
                    (bold and 'b'),
                    (underline and 'u'),
                    ('f%x' % ([fg, bg][reverse])),
                    ('b%x' % ([bg, fg][reverse])),
                    (reverse and 'r'),
                    )))
                for n, t in enumerate(re_hyperlink.split(txt)):
                    if n % 2:
                        s = style + ('link',)
                    else:
                        s = style
                    self.buffer.insert(END, t, s)

        if scroll > 0.999:
            self.buffer.see(END)

    def get_channel(self, quiet=False):
        if self.channel_num is not None:
            return self.channels[self.channel_num]
        elif not quiet:
            self.write_text('\x0304---\x0305 Not in channel')
        return False


    def is_me(self, nick):
        return nick == self.nick

    def highlight(self, text):
        try:
            hre = self._highlight_re
        except AttributeError:
            terms = filter(None, cfg.highlight)
            if terms:
                # TODO wildcards?
                hre = re.compile(r'\b(' + '|'.join(map(re.escape, filter(None, terms))) + r')\b', re.IGNORECASE)
            else:
                hre = False
            self._highlight_re = hre
        if not hre:
            return False

    def ignore(self, event, channel):
        """event is a letter:
            j = join
            p = part
            q = quit
            n = nick
        If channel is None, return the default for all channels."""
        return event in (self.ignores.get(channel or '*', self.ignores.get('*')) or '')

    # server events
    def on_unknown_numeric(self, src, num, args):
        self.write_text(' '.join(args[1:]))

    # Welcome to IRC
    def on_001(self, src, cmd, args):
        realnick = args[0]
        if not self.is_me(realnick):
            self.nicks.appendleft(self.nick)
            self.nick = realnick
        self.write_text(' '.join(args[1:]))
        # autojoin channels
        if self.autojoin:
            c, k = zip(*sorted(self.autojoin.items(), key=itemgetter(1), reverse=True))
            c, k = ','.join(c), ','.join(itertools.takewhile(lambda x: x, k))
        else:
            c = k = None
        if c:
            if k:
                k = ' ' + k
            self.send('JOIN %s%s' % (c, k))
        self.connected = True
        self.reconnect = True
        self.lag_waiting = False
        self.lag_monitor()

    def on_375(self, src, cmd, args): # RPL_MOTDSTART
        if not cfg.hush_motd:
            self.write_text(' '.join(args[1:]))
    on_372 = on_375 # RPL_MOTD
    def on_376(self, src, cmd, args): # RPL_ENDOFMOTD
        if cfg.hush_motd:
            self.write_text('MOTD skipped')
        else:
            self.write_text(' '.join(args[1:]))
        self.connected = True

    def on_005(self, src, cmd, args):
        args = args[1:]
        caps = dict([(c.split('=', 1) + [''])[:2] for c in args])
        if 'CAPAB' in caps:
            # silly freenode stuff
            self.send('CAPAB IDENTIFY-MSG')
        self.channel_types = caps.get('CHANTYPES', self.channel_types)
        # TODO: character set and mapping nonsense
        self.write_text(' '.join(args))

    def on_290(self, src, cmd, args):
        if self.identify_msg:
            # we've already done this internally,
            # perhaps for some reason the user explicitly did a /capab
            self.write_text(' '.join(args[1:]))
        elif 'IDENTIFY-MSG' in args:
            self.identify_msg = True

    def on_433(self, src, cmd, args): # ERR_NICKNAMEINUSE
        _, errnick, message = args
        self.write_text('\x0304---\x0305 %s: %s' % (errnick, message))
        if not self.connected:
            self.nicks.append(self.nick)
            self.nick = self.nicks.popleft()
            self.write_text('\x0314--- Retrying with %s' % self.nick)
            self.send('NICK %s' % self.nick)

    def on_331(self, src, cmd, args): # RPL_NOTOPIC
        _, channel, message = args
        channel = channel.lower()
        self.write_text('\x0314--- %s' % message, channel)
    def on_332(self, src, cmd, args): # RPL_TOPIC
        _, channel, topic = args
        channel = channel.lower()
        self.write_text('\x0314--- Topic is: %s' % topic, channel)
    def on_333(self, src, cmd, args): # RPL_TOPICWHOTIME
        _, channel, nick, timestamp = args
        channel = channel.lower()
        timestamp = int(float(timestamp)) # might break?
        self.write_text('\x0314--- Topic set by %s at %s' % (nick, time.ctime(timestamp)), channel)

    def on_324(self, src, cmd, args): # RPL_CHANNELMODEIS
        channel = args[1]
        modes = ' '.join(args[2:])
        self.write_text('\x0314--- Mode is %s' % modes, channel)

    def on_353(self, src, cmd, args): # RPL_NAMREPLY
        nick, blah, channel, names = args
        channel = channel.lower()
        if channel not in self.channel_namelist:
            # Hey, we didn't ask for this!
            return
        self.channel_namelist[channel].update(names.split())
    def on_366(self, src, cmd, args): # RPL_ENDOFNAMES
        nick, channel = args[:2]
        channel = channel.lower()
        try:
            names = sorted(self.channel_namelist.pop(channel))
        except KeyError:
            return
        self.write_text(' '.join(map('\x0314[\x0301,99%s\x0314]\x0f'.__mod__, names)), channel)

    def on_error(self, src, cmd, args):
        self.write_text('\x0304***\x0305 %s' % ' '.join(args))

    def on_ctcp_action(self, src, cmd, args):
        nick = src.split('!')[0]
        channel, text = args
        # channel = channel.lower() # already done by privmsg

        if cfg.strip_control:
            text = strip_control(text)
        hl = self.highlight(text)
        if hl:
            text = hl
            format = '\x0304* \x0305,99\x02%s\x02\x0304 %s'
        else:
            format = '\x0314* \x03%02d,99%%s\x0f %%s' % random_color(src, cfg.nickcolors)
        self.write_text(format % (nick, text), channel)

    def on_ctcp_ping(self, src, cmd, args):
        nick = src.split('!')[0]
        channel, text = args
        self.write_text('\x0314*** Received a CTCP PING from %s' % (nick), channel)
        self.send('NOTICE %s :\x01PING %s\x01' % (nick, text))

    def on_ctcpr_ping(self, src, cmd, args):
        nick = src.split('!')[0]
        channel, text = args
        try:
            lag = decode_ping_time(text)
        except:
            lag = '???'
        else:
            lag = '%.2f' % (time.time() - lag)
        self.write_text('\x0314--- Ping reply: %s seconds' % (lag), nick)

    def on_privmsg(self, src, cmd, args):
        nick = src.split('!')[0]
        channel, text = args
        channel = channel.lower()

        # freenode junk
        if self.identify_msg and text and text[0] in '+-':
            if text[0] == '-':
                nick += '?'
            text = text[1:]

        if text.startswith('\x01') and text.endswith('\x01'):
            text = text[1:-1]
            try:
                ctcp, text = text.split(' ', 1)
            except ValueError:
                ctcp, text = text, ''
            handler = getattr(self, ('on_ctcp_%s' % ctcp).lower(), None)
            if handler:
                handler(src, ctcp, [channel, text])
            else:
                self.write_text('\x0314*** Received a CTCP %s from %s%s'
                        % (ctcp, nick, text and ': ' + text or ''), channel)
            return

        if cfg.strip_control:
            text = strip_control(text)
        hl = self.highlight(text)
        if hl:
            text = hl
            format = '\x0304<\x0305,99\x02%s\x02\x0304> %s'
        else:
            # src or nick?
            format = '\x0314<\x03%02d,99%%s\x0314>\x0f %%s' % random_color(src, cfg.nickcolors)
        self.write_text(format % (nick, text), channel)

    def on_notice(self, src, cmd, args):
        nick = src.split('!')[0]
        channel, text = args
        channel = channel.lower()

        if text.startswith('\x01') and text.endswith('\x01'):
            text = text[1:-1]
            try:
                ctcp, text = text.split(' ', 1)
            except ValueError:
                ctcp, text = text, ''

            handler = getattr(self, ('on_ctcpr_%s' % ctcp).lower(), None)
            if handler:
                handler(src, ctcp,p [channel, text])
            else:
                self.write_text('\x0314*** Received a CTCP %s reply from %s%s'
                        % (ctcp, nick, text and ': ' + text or ''), channel)
            return

        self.write_text('\x0314-\x0303%s\x0314-\x0f %s' % (nick, text), channel)

    def on_join(self, src, cmd, args):
        nick = src.split('!')[0]
        channel = args[0]
        channel = channel.lower()

        if self.is_me(nick):
            self.list_channel(channel)
            self.write_text('\x0314--- Now talking in %s' % channel)
        elif not self.ignore('j', channel):
            self.write_text('\x0314*** Join: %s' % src, channel)

    def on_part(self, src, cmd, args):
        nick = src.split('!')[0]
        channel = args[0]
        channel = channel.lower()

        text = ' '.join(args[1:])
        if text:
            text = ' (' + text + ')'

        if self.is_me(nick):
            self.write_text('\x0314--- No longer talking in %s%s' % (channel, text))
            self.delist_channel(channel)
        elif not self.ignore('p', channel):
            self.write_text('\x0314*** Part: %s%s' % (nick, text), channel)

    def on_mode(self, src, cmd, args):
        nick = src.split('!')[0]
        channel = args[0]
        modes = ' '.join(args[1:])
        self.write_text('\x0314*** %s sets mode: %s' % (nick, modes), channel)

    # TODO: on_kick, on_topic

    def on_quit(self, src, cmd, args):
        nick = src.split('!')[0]
        text = ' '.join(args)
        if text:
            text = ' (' + text + ')'
        if not self.ignore('q', None):
            self.write_text('\x0314*** Quit: %s%s' % (nick, text))

    def on_nick(self, src, cmd, args):
        oldnick = src.split('!')[0]
        newnick = args[0]
        if oldnick == self.nick:
            self.nick = newnick
            self.write_text('\x0314--- Now known as %s' % newnick)
        elif not self.ignore('n', None):
            self.write_text('\x0314*** %s is now known as %s' % (oldnick, newnick))

    def on_ping(self, src, cmd, args):
        self.send('PONG :' + ' '.join(args))

    def on_pong(self, src, cmd, args):
        try:
            _, token = args
            pingtime = decode_ping_time(token)
        except (IndexError, ValueError):
            pass
        else:
            self.lag_waiting = False
            self.lag = time.time() - pingtime
            return
        self.write_text('\x0314*** PONG ' + ' '.join(args))

    def lag_monitor(self):
        if self.lag_waiting:
            self.write_text('\x0304---\x0305 No response from server; closing link')
            try:
                self.send('QUIT')
            except:
                pass
            self.connect()
            return
        self.lag_waiting = True
        self.send('PING :%s' % encode_ping_time())
        self.after(1000 * 60, self.lag_monitor) # once a minute

    def io_poll(self):
        try:
            data = self.socket.recv(1024)
        except socket.error, e:
            if e.args[0] != errno.EWOULDBLOCK:
                # blah
                self.socket = None
                self.connected = False
                self.write_text('\x0304---\x0305 Socket error: %s' % e.args[1])
                self.write_text('\x0304---\x0305 Reconnecting in 60 seconds...')
                self.after(1000 * 60, self.connect)
                raise
        except AttributeError:
            self.connected = False
            return
        else:
            conn_closed = not data
            data = data.decode(self.encoding, 'replace')
            self.io_callback(data)
            if conn_closed:
                self.socket.close()
                self.socket = None
                self.connected = False
                self.write_text('\x0314--- Connection closed by remote host.')
                if self.reconnect:
                    self.connect()
                    return # don't reconnect io_poll; connect will do that once it's up
        self.after(100, self.io_poll) # 1/10 second

    def io_callback(self, data):
        if DEBUG:
            print('< %r' % data)

        data = linesplit(self.leftover + data)
        self.leftover = data.pop()
        for line in data:
            try:
                parts = line.split(' :', 1)
                args = filter(None, parts[0].split(' ') + parts[1:])
                if not args:
                    continue # weird
                if args[0].startswith(':'):
                    src = args.pop(0)[1:]
                else:
                    src = ''
                cmd = args.pop(0)

                if re.match(r'^\d\d\d$', cmd):
                    fallback = self.on_unknown_numeric
                elif re.match(r'^\w+$', cmd):
                    fallback = lambda src, cmd, args: self.write_text(line)
                else:
                    raise ValueError, 'mismatch'
                handler = getattr(self, ('on_%s' % cmd).lower(), fallback)
                handler(src, cmd, args)
            except Exception, e:
                self.write_text('\x0304???\x0314 %s' % line)
                tb = ''.join(traceback.format_exception(*sys.exc_info()))
                if DEBUG:
                    print(tb, file=sys.stderr)
                    errtext = e
                else:
                    errtext = tb
                self.write_text('\x0304***\x0305 %s:\x0f\n\x0314%s' % (e.__class__, errtext))


    # client commands

    def cmd_privmsg(self, cmd, args):
        try:
            context = args.pop(0).strip()
        except IndexError:
            self.write_text('\x0304---\x0305 Usage: /%s <target> <message>' % cmd.upper())
        line = ' '.join(args)
        self.write_text('\x0315<\x0314%s\x0315>\x03 %s' % (self.nick, line), context)
        self.send('PRIVMSG %s :%s' % (context, line))
    cmd_msg = cmd_privmsg

    def cmd_say(self, cmd, args):
        channel = self.get_channel()
        if channel:
            args.insert(0, channel)
            self.cmd_privmsg(cmd, args)

    def _ctcp_helper(self, cmd, args, ctcpr, servercmd):
        context, ctcp, line = args[0].strip(), args[1].strip().upper(), ' '.join(args[2:])
        if ctcpr:
            ctcpr = ctcp + ' reply' # bah
        self.write_text('\x0315---\x0315 Sent CTCP %s%s' % (ctcpr or ctcp, line and ': ' + line or ''), context)
        self.send('%s %s :\x01%s%s' % (servercmd, context, ctcp, line and ' ' + line or ''))
    def cmd_ctcp(self, cmd, args):
        self._ctcp_helper(cmd, args, False, 'PRIVMSG')
    def cmd_ctcpr(self, cmd, args):
        self._ctcp_helper(cmd, args, True, 'NOTICE')

    def cmd_action(self, cmd, args):
        context = args.pop(0).strip()
        line = ' '.join(args)
        self.write_text('\x0315*\x0314 %s\x03 %s' % (self.nick, line), context)
        self.send('PRIVMSG %s :\x01ACTION %s\x01' % (context, line))
    cmd_act = cmd_action

    def cmd_me(self, cmd, args):
        channel = self.get_channel()
        if channel:
            args.insert(0, channel)
            self.cmd_action(cmd, args)

    def cmd_notice(self, cmd, args):
        try:
            context = args.pop(0).strip()
        except IndexError:
            self.write_text('\x0304---\x0305 Usage: /%s <target> <message>' % cmd.upper())
        line = ' '.join(args)
        self.write_text('\x0315-\x0314%s\x0315-\x03 %s' % (self.nick, line), context)
        self.send('NOTICE %s :%s' % (context, line))

    def cmd_names(self, cmd, args):
        if not args:
            channel = self.get_channel()
            if not channel:
                return
            args.insert(0, channel)
        for channel in args:
            if not channel.strip():
                continue
            self.channel_namelist[channel.lower()] = set()
            self.send('NAMES %s' % channel)

    def cmd_part(self, cmd, args):
        try:
            channels = args.pop(0)
        except:
            channels = self.get_channel()
            if channels is None:
                return
        reason = ' '.join(args)

        part = set()
        for arg in channels.split(','):
            if self.is_channel(arg):
                part.add(arg.lower())
            else:
                self.delist_channel(arg)
            if part:
                if reason:
                    reason = ' :' + reason
                self.send('PART %s%s' % (','.join(part), reason)) # join part? what?
    cmd_close = cmd_part

    def cmd_query(self, cmd, args):
        try:
            nick = args.pop(0)
        except IndexError:
            self.write_text('\x0304---\x0305 Usage: /QUERY <nick> [message]')
        else:
            nick = nick.strip()
            self.list_channel(nick)
            if args:
                args.insert(0, nick) # blah
                self.cmd_privmsg(cmd, args)

    def cmd_print(self, cmd, args):
        self.write_text(' '.join(args))
    cmd_echo = cmd_print

    def cmd_ping(self, cmd, args):
        try:
            nick = args.pop(0)
        except IndexError:
            self.write_text('\x0304---\x0305 Usage: /PING <nick>')
        else:
            self.send('PRIVMSG %s :\x01PING %s\x01' % (nick, encode_ping_time()))

    def cmd_eval(self, cmd, args):
        line = ' '.join(args)
        o, e = sys.stdout, sys.stderr
        io = sys.stdout = sys.stderr = StringIO()
        exec line in globals(), {'self': self}
        sys.stdout, sys.stderr = o, e
        result = io.getvalue().strip()
        if result:
            self.write_text(result)
    cmd_python = cmd_py = cmd_eval

    # TODO: on quit, clear channel list and timers
    def cmd_quit(self, cmd, args):
        line = ' '.join(args) or cfg.quit_message
        self.reconnect = False
        self.write_text('\x0314--- Quit: %s' % line)
        self.send('QUIT :%s' % line)
    cmd_exit = cmd_quit

    def cmd_raw(self, cmd, args):
        self.send(' '.join(args))
    cmd_quote = cmd_verbose = cmd_raw

    def cmd_lag(self, cmd, args):
        self.write_text('\x0314--- Server lag: %.3f seconds' % self.lag)


    # widget bindings

    def history_change(self, delta):
        histlen = len(self.history)
        if not histlen:
            return
        self.history_ptr = (self.history_ptr + histlen + delta) % histlen
        self.textentry.set(self.history[self.history_ptr])
        self.textentry.widget.icursor(END)
    def history_prev(self):
        self.history_change(-1)
    def history_next(self):
        self.history_change(1)

    def history_add(self, line):
        if not line:
            return
        while line in self.history:
            self.history.remove(line)
        self.history.pop(0)
        self.history.append(line)
        self.history = self.history[-HISTORY_LEN:]
        self.history.insert(0, '')
        self.history_ptr = 0

    def eval_line(self, line):
        def no_handler(cmd, args):
            # give all unknown /commands straight to the server
            self.send('%s %s' % (cmd.upper(), ' '.join(args)))

        if not line:
            return
        if line.startswith(cfg.cmd_prefix):
            args = argsplit(line[len(cfg.cmd_prefix):])
            cmd = args.pop(0)
            handler = getattr(self, ('cmd_%s' % cmd).lower(), no_handler)
            try:
                handler(cmd, args)
            except Exception, e:
                tb = ''.join(traceback.format_exception(*sys.exc_info()))
                if DEBUG:
                    print(tb, file=sys.stderr)
                    errtext = e
                else:
                    errtext = tb
                self.write_text('\x0304***\x0305 %s:\x0f\n\x0314%s' % (e.__class__, errtext))
        else: # default to /say
            self.cmd_say('', [line])

    def handle_input(self):
        line = self.textentry.get()
        self.history_add(line)
        lines = linesplit(line)
        self.textentry.set('')
        for line in lines:
            self.eval_line(line)
        self.buffer.see(END) # always do this, even if we were scrolled back

    def delist_channel(self, channel):
        current = self.get_channel(False)
        while channel in self.channels:
            self.channels.remove(channel)
        if not self.channels:
            self.channel_num = None
            self.prompt.set(self.network)
            return
        try:
            self.channel_num = self.channels.index(current)
        except ValueError:
            self.channel_num = max(0, self.channel_num - 1)
            self.prompt.set(self.channels[self.channel_num])

    def list_channel(self, channel):
        if channel not in self.channels:
            self.channels.append(channel)
            self.channels.sort()
        self.channel_num = self.channels.index(channel)
        self.prompt.set(self.channels[self.channel_num])

    def rotate_channel(self, delta):
        if self.channel_num is None:
            return
        t = len(self.channels)
        self.channel_num = (self.channel_num + t + delta) % t
        self.prompt.set(self.channels[self.channel_num])
    def prev_channel(self):
        self.rotate_channel(-1)
    def next_channel(self):
        self.rotate_channel(1)

    def window_close(self):
        try:
            self.send('QUIT :%s' % cfg.quit_message)
        except:
            pass
        self.destroy()

    def join_prompt(self):
        s = (tkSimpleDialog.askstring('irc', 'Channel name:') or '').strip()
        if not s:
            return
        if s[0] not in self.channel_types:
            s = '#' + s
        self.eval_line('/join %s' % s)

    # main screen turn on
    def __init__(self, network, server, port, password, nicks, username, realname, channels, ignores, encoding):
        Tk.__init__(self, None)

        self.geometry(cfg.geometry)
        self.autojoin = dict([tuple(c.split(None, 1) + [None])[:2] for c in channels])
        self.network = network
        self.channels = []
        self.channel_num = None
        # /names output -- channel: [nick, nick, nick...]
        self.channel_namelist = {}
        self.channel_types = '#&'
        self.server = server
        self.port = port
        self.password = password
        self.encoding = encoding
        self.nicks = deque(nicks)
        if len(self.nicks) < 1:
            self.nicks.append(self.username)
        while len(self.nicks) < 3:
            self.nicks.append('_%s_' % (self.nicks[-1]))
        self.nick = self.nicks.popleft()
        self.username = username
        self.realname = realname
        self.ignores = ignores

        self.history = ['']
        self.history_ptr = 0
        self.lag = 0
        self.identify_msg = False # freenode

        self.title('%s - Paperplane' % network)
        if os.name == 'nt':
            self.option_add('*font', 'Tahoma 8')

        self.protocol('WM_DELETE_WINDOW', self.window_close)

        # create widgets
        topframe = Frame(self)
        topframe.pack(expand=True, fill=BOTH, side=TOP)
        bottomframe = Frame(self)
        bottomframe.pack(expand=False, fill=BOTH, side=TOP)

        self.buffer = ScrolledText(topframe, font=cfg.font, wrap=WORD, height=0)
        self.buffer.scrollbar = self.buffer.pack_slaves()[0]
        assert isinstance(self.buffer.scrollbar, Scrollbar)
        self.buffer.pack(expand=True, fill=BOTH, side=LEFT)
        self.prompt = StringVar()
        self.prompt.set(self.network)

        def callback(func, *args, **kw):
            return lambda e: (func(*args, **kw), 'break')[1]
        def nop(e):
            return 'break'

        label = Label(bottomframe, textvariable=self.prompt)
        label.pack(side=LEFT)
        self.textentry = StringVar()
        self.textentry.widget = entry = Entry(bottomframe, textvariable=self.textentry)
        entry.pack(expand=True, fill=X, side=LEFT)
        entry.focus_set()

        self.bind('<Control-p>', callback(self.prev_channel))
        self.bind('<Control-n>', callback(self.next_channel))
        self.bind('<Control-w>', callback(self.cmd_part, '', []))
        self.bind('<Control-q>', callback(self.window_close))
        self.bind('<Control-j>', callback(self.join_prompt))

        entry.bind('<Return>', callback(self.handle_input))
        entry.bind('<Up>', callback(self.history_prev))
        entry.bind('<Down>', callback(self.history_next))

        # fix some of tkinter's screwiness
        entry.bind('<Control-slash>', nop)
        self.buffer.bind('<Control-slash>', nop)
        entry.bind('<Control-a>', callback(entry.selection_range, 0, END))
        def delete_word():
            t = entry.get()[:entry.index(INSERT) - 1]
            try:
                pos = t.rindex(' ') + 1
            except ValueError:
                pos = 0
            entry.delete(pos, INSERT)
        entry.bind('<Control-BackSpace>', callback(delete_word))
        entry.bind('<Alt-BackSpace>', callback(delete_word))

        for k, c in [
            ('b', FC_BOLD),
            ('k', FC_COLOR),
            ('g', FC_BEEP),
            ('o', FC_RESET),
            ('r', FC_REVERSE),
            ('i', FC_ITALIC),
            ('m', FC_MONOSPACE),
            ('u', FC_UNDERLINE),
        ]:
            entry.bind('<Control-%s>' % k, callback(entry.insert, INSERT, chr(c)))

        self.buffer.bind('<Tab>', callback(entry.focus_set))
        self.buffer.bind('<Return>', callback(entry.focus_set))
        self.buffer.bind('<Control-a>', callback(self.buffer.tag_add, SEL, '1.0', END))

        # styles
        self.buffer.tag_config('b', font=cfg.bold_font)
        self.buffer.tag_config('u', underline=True)
        for c in xrange(16):
            self.buffer.tag_config('f%x' % c, foreground=cfg.colors[c])
            self.buffer.tag_config('b%x' % c, background=cfg.colors[c])

        self.buffer.tag_config('link', foreground=cfg.colors[12], underline=True)
        def link_click(e):
            url = self.buffer.get(*self.buffer.tag_prevrange('link', '@%d,%d' % (e.x, e.y)))
            webbrowser.open(url)
        self.buffer.tag_bind('link', '<Enter>', lambda e: self.buffer.config(cursor='hand2'))
        default = self.buffer.config('cursor')[-1]
        self.buffer.tag_bind('link', '<Leave>', lambda e: self.buffer.config(cursor=default))
        self.buffer.tag_bind('link', '<Button-1>', link_click)

        self.buffer.tag_raise(SEL)

        # now for the real fun
        self.socket = None
        self.connected = False
        self.reconnect = False
        self.connect()

if __name__ == '__main__':
    #sys.stderr = file('error.log', 'w')
    for s in cfg.servers:
        server = s.get('server', None)
        if server and s.get('enabled', True):
            IrcWindow(
                s.get('network', server),
                server,
                s.get('port', 6667),
                s.get('password', None),
                s.get('nicknames', cfg.nicknames),
                s.get('username', cfg.username),
                s.get('realname', cfg.realname),
                s.get('channels', []),
                s.get('ignores', {}),
                s.get('encoding', 'utf-8'),
            )
    mainloop()
