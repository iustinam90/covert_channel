
Covert channel using CPU/bandwidth. Tested with KVM and VMware
Author: Iustina Melinte

=== Setup

2 Centos 6.0 with NTP enabled (System > Administration > Date & Time, add new..etc). 

If testing with CPU:
cpu pinning as in:
http://www.linux-kvm.com/content/tip-running-your-vm-specific-cpus
( virsh vcpuinfo guest_name,  taskset -p 0x00000001 _pid (grep pid /var/run/libvirt/qemu/guest1.xml)  )

If testing with bandwidth :
-Scapy installed 
-the ncat server listening : ncat -l 172.16.186.1 1234 -k -m 1

There must be a file named 'inp' which contains the message to be sent, in the same dir as the script. (harcoded the filename to avoid putting to many parameters,mhm)

Usage: 
covert.py s|d max_for_0 min_for_1 [srv_ip srv_port] (max_for_0 could be > min_for_1)
covert.py bench num_times [srv_ip srv_port]

First, benchmark when alone:
	python covert.py bench 20
..then when both are running:
	python covert.py bench 20
The output gives the max and min number of pkts that can be sent in one second. Use the min from (1) output as min_for_1 and the max from (2) as the max_for_0 to start the sender:
	python covert.py s max_for_0 min_for_1 [srv_ip srv_port]
..and the receiver:
	python covert.py d max_for_0 min_for_1 [srv_ip srv_port]

CPU:
	python covert.py s 552224 894315
	python covert.py d 552224 894315
If max_for_0<min_for_1, then these values are automatically increased/decreased equally to fill the gap interval. 

Bandwidth:
eg. if no overlapping interval for '1' and '0':
	python covert.py s 200 201 172.16.186.1 1234
	python covert.py d 200 201 172.16.186.1 1234
..or with overlapping interval:
	python covert.py s 200 190 172.16.186.1 1234
	python covert.py d 200 190 172.16.186.1 1234

('transmitter' and 'receiver' are _not_ sending pkts to each other)

=== Idea

- use CPU intensive operation
..tested with KVM: the difference between the number of operations (pow(2,12)) per sec when running alone or both vms is quite big, such as : 552224(max when both) and 894315(min when alone)

..Or calculate network bandwidth pkts/sec. Tested with VMware: found that when both are transmitting, the bw <200 pkts/sec and when only one is transmitting, the bw>200. But the intervals overlap sometimes. So if bw<200 we take it as a '0' and if bw>200, a '1'. The packet sent is a SYN to the ncat open port

- use ascii printable characters. 
skip the first bit (always a '0') - so we use 7bits per char
use '000000' as a message delimiter (no used char contains it)

- fixed-length 'frames' - 8 chars + 6 chars ('FCS')
FCS = sum of bits :).. we needed smth small 

- try error correction if ( calculated FCS - provided FCS ) <=4
 the unknown bits (denoted by '?', when the calculated bandwidth matches the overlapping interval for '0' and '1') are used as wildcards to match valid characters. It appears as a list inside the text such as 'a[pP]ple'
 if the character doesn't seem to be valid, a '?' is put in place of it in the text


=== Flow

before:
- calculate max and min bandwidth when both/one are/is sending
- precompute the frames from ascii text file (so that it won't take time during transmission) 

step 1
synchronize with the peer : 
at startup, send pkts to the server for 1 sec when int(time)%5==0 (every 5 sec)
when pkts < 200 it means that the peer is there and we go to step 2 
works every time :P

step 2
Transmit one frame at a time and wait for receiver to send back a notification:
'0000' means there was a fcs error and the sender will retransmit the same frame
'1111' - no error, go to next frame
After all frames are transmitted, a message delimiter is sent ('1111111') so that the receiver will stop listening for transmissions and go back to the synchronization state (state 1, when it checks the bw every 5 sec). 
This delimiter could also mean that the sender crashed (since '1' means no 
pkts are being sent).
The receiver verifies constantly that this delimiter is not present in the current frame that it constructs, so it can detect when the sender stopped unexpectedly. So if it receives more than 6 '0's and the farme length is less than 56+6(fcs), then the sender is gone.

After sending the msg the sender stops, but the receiver remains and waits for a new synchronization to happen (and then a new transmission) in a infinite loop. 

=== Facts & Fails 

- slow communication
- skipping time slots (=bits) (very rare). When it happens, the FCS check fails and the frame is retransmitted
- sometimes they think they sinchronized at different moments..(very rare too)

Might fail when..
.. the clocks are not synchronized
.. other apps use the network and/or take up the CPU 


=== Tests

see the 'test' directory.


=== Other ideas

silly one: if ncat is listening like "ncat -l 1234 -k --broker" then the machines can chat :P

