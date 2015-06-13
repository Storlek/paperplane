Paperplane: a paperweight IRC client

Copyright (c) 2006-2015 Storlek


# About

Paperplane is a very minimal IRC client that displays all activity in
a single window. It's about as bare as you can get while still having
a proper GUI, but manages to be flexible and quite usable despite its
size.

It was designed for monitoring purposes on an airgapped network, and
gained some popularity for somehow being better than any of the other
clients that were available.


# Usage

1. edit `ircconfig.py` to suit your needs
2. run `irc.py` using Python 2.x
   (if you're using Windows, you might be able to rename `irc.py` to
   `irc.pyw` to make it double-clickable)


## Key bindings

Ctrl-P/N: change channel  
Ctrl-W: part channel  
Ctrl-Q: quit  
Ctrl-J: prompt to join channel  
Up/Down: history


## Formatting

mIRC-style text formatting is supported, with some additions inspired
by (believe it or not) MS Comic Chat.

Ctrl-B: bold  
Ctrl-K: color  
Ctrl-G: beep!  
Ctrl-O: reset all formatting  
Ctrl-R: reverse  
Ctrl-I: italic  
Ctrl-M: monospace  
Ctrl-U: underline


## Client commands

    /nick newname

Change your name.

    /join #channel
    /part #channel

Join or leave a channel.

    /quit your quit message...

Send a quit message the server, close the connection, and exit.

    /query someone

Open a private message context for an individual IRC user.

    /lag

Display the server's round-trip time.

    /names

Get a list of users in the current channel context.

    /msg #channel Hi everybody!
    /msg DrNRiviera Hi, Doctor Nick!
    /say hello
    /me does a thing
    /action #channel does a thing
    /notice someone Hey this is a -notice-

Various ways to send messages.
Of course, just typing a line of text usually works fine.

    /eval python_code

For example, /eval dir() or /eval self.title = "sup"



## Warning

Be mindful of the selected channel when you're typing! It can
sometimes be easy to forget where you are when you're watching
activity from several places at once.


# Bugs

- Even though you can configure a bunch of servers,
  only one window will function at a time, because lol Tk
- Character encodings are totally ignored, sorry :(
- SSL is not supported and likely never will be


# Author

Storlek <storlek@rigelseven.com>


# License

The MIT License (MIT)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
