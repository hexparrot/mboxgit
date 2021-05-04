# mboxgit
python script converts mbox to git repo as alternative fileshare

# downloading

    $ sudo dnf install git git-secret gpg
    $ sudo dnf install nmap-ncat #optional
    $ git clone https://github.com/hexparrot/mboxgit.git
    $ cd mboxgit
    $ ./convert --help

# usage

open .mbox file as argument to -m:

    $ ./convert -m rf-mime-torture-test-1.0.mbox

to use encryption, provide an email address that matches
a public key registered on the host system in gpg:

    $ gpg --list-keys | grep uid
      uid           [ultimate] William Dizon <will@local>

    $ ./convert -m rf-mime-torture-test-1.0.mbox -e will@local

# transferring

open a netcat server on the host to serve `commit.tar`:

    $ ./serve
    
or

    $ cat commit.tar | nc --send-only -4 -l -p 8888    # this is the equivalent

on the destination node, receive the file:

    $ nc [hostname/ip] 8888 > commit.tar < /dev/null
    
