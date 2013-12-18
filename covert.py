from scapy.all import *
from pprint import pprint as pp
import time,sys,re

inp="inp"

wait_sec_mod=5
bw_max_0=0 #200
bw_min_1=0 #201

bench_sec={'s':0,'d':3,'mod':6}
send_sec_mod=2 # sec, for synchronization
bench_time=1 #  sec
default_num_bench=10

frame_len=8 # bytes
fcs_len=6 #bits
ch_len=7 # skip first bit (always 0)

ncat_srv=''#"172.16.186.1"
ncat_srv_port=0 #1234


def bench(num_times):
    num_bench=num_times
    bw_min_1s=[]
    # benchmark when transmitting alone or both in a time slot
    while(num_bench):
        t=time.time()
        if(int(t)% 2== 0):
            n=0
            while(time.time()-t<bench_time):
                pkt=IP(dst=ncat_srv)/TCP(dport=ncat_srv_port,flags="S")
                send(pkt)#,verbose=0)
                n+=1
            print "_ bench",n
            bw_min_1s.append(n)
            time.sleep(0.8)
            num_bench-=1

    print '_ min ',min(bw_min_1s)
    print '_ max ',max(bw_min_1s)
                
            
def get_bw(t):
    n=0
    while(time.time()-t<bench_time):
        pkt=IP(dst=ncat_srv)/TCP(dport=ncat_srv_port,flags="S")
        send(pkt)#,verbose=0)
        n+=1
    return n

def get_bit_type(bw):
    if(bw<=bw_max_0 and bw>=bw_min_1):
        return '1' #todo I set this randomly
    if(bw<=bw_max_0):
        return '0'
    if(bw>=bw_min_1):
        return '1'

def recv_fr():
    prev_t=None
    frames=[]
    while(1):
        ok=0
        while(not ok):
            recv_size=0
            frame=''
            myfcs=0
            num1s=0 #consecutive
            while(recv_size<frame_len*ch_len+fcs_len): 
                t=time.time()
                if(int(t)% send_sec_mod == 0):
                    if(not prev_t): prev_t=int(t)
                    if(int(t)-prev_t>send_sec_mod):
                        print '_ !! skipped slot'
                    prev_t=int(t)
                    bw=get_bw(t) # watch 1 sec
                    bit=get_bit_type(bw)
                    frame+=bit
                    print '_ recv',bw,t,frame   
                    if(bit=='1'):
                        num1s+=1
                        if(num1s>=7):
                            print "_ end of message(delimiter or sender crashed)"
                            return frames# end of message(delimiter or sender crashed), go back to listening  
                    else: num1s=0       
                    recv_size+=1
                    time.sleep(0.9)

            #check fcs at end of frame,if +-4 notify #### AFTER: decide what are '?'s,
            his_fcs=int(frame[-6:],2) 
            my_fcs=sum(int(x) for x in re.findall('1',frame[:-6]))
            if(his_fcs==my_fcs):
                ok=1
                print '_ fcs ok',frame
                frames.append(frame)
                time.sleep(3*send_sec_mod)
            else: # notify sender
                count=3
                print '_ fcs bad,ask resend (send 3 "0"s)',frame
                while(count):
                    t=time.time()
                    if(int(t)% send_sec_mod == 0):
                        bw=get_bw(t) # send a '0' 
                        print '_ sent a 0',bw,t
                        count-=1
                        time.sleep(0.9)
        
def get_msg(frames):
    print '_ recv frames'
#    frames=['11000011110011110010011000011100100000101011001001100001011001','11100111100110000101001100000110000011000001100000110000010101']
    for fr in frames: print '_ ',fr
    msg=''
    for fr in frames:
        chars_bin=[fr[i:i+ch_len] for i in range(0,len(fr)-6,ch_len)]
        for ch_bin in chars_bin:
            msg+=chr(int(ch_bin,2))
    print '_ msg',msg        
    
    
#  eg. frames [('11000011110011110010011000011100100000101011001001100001011001',2), .. ]
def get_msg_with_correction(frames):
#    frames=[('100000110000011000001100?0011000010?00001010000101000010',2),
# ('11000111?00?11100001110000111000100100010010001001000100',3),
# ('10001011000101100010110001011000110100011010001101000110',0),
# ('000101011000011110011110010011000011100100000101011001?0',1),
# ('11000011110011110010011101101100001110010011101101100010',0),
# ('11000100001010011000001100000110000011000001100000110000',0)]
    
    print '_ recv frames'
    for fr in frames: print '_ ',fr
    msg=''
    append_msg='Errors unidentified:'
    # construct possible chars array
    valid_chars_int=[10,13]+range(32,127)
    valid_chars_bin=[] # eg ['0100000','0100001',..]
    for ch_int in valid_chars_int:
        ch_bin=bin(ch_int)[2:] 
        valid_chars_bin.append('0'*(ch_len-len(ch_bin))+ch_bin) # ensure it it 7 bits len
        
    for (fr_bin,fcs_err) in frames:
        chars_bin=[fr_bin[i:i+ch_len] for i in range(0,len(fr_bin)-6,ch_len)]        
        if(fcs_err):
            for ch_bin in chars_bin:
                pos=ch_bin.find('?')
                possible_ch=[]
                if(pos>-1):  # correct '?'s
                    fcs_err-=1
                    for valid_ch_bin in valid_chars_bin:
                        found=re.search(ch_bin.replace('?','[01]'),valid_ch_bin) # eg re.search('11?1?10'.replace('?','[01]'),'1111110')
                        if(found):
                            possible_ch.append(chr(int(valid_ch_bin,2)))
                    if(len(possible_ch)>1):
                        msg+='['+','.join(possible_ch)+']'
                    else:
                        msg+=possible_ch[0]
                    print "identified",possible_ch
                else: # no ? inside char, see if it is valid
                    if(fcs_err>0 and (not ch_bin in valid_chars_bin)):
                        msg+='?'
                        fcs_err-=1
                        print "identified",ch_bin
                    else:
                        msg+=chr(int(ch_bin,2))
                        
            if(fcs_err>0): # we didn't identified all errors
                append_msg+='+'+str(fcs_err)
                print "unidentified"
        else: # no fcs err, append the chars 
            for ch_bin in chars_bin:
                msg+=chr(int(ch_bin,2))
    print '_ msg',msg,'\n',append_msg        
    
    
def receiver():
    sec_mod=wait_sec_mod
    num0=0; started=0
    while(1): #not started
        t=time.time()
        if(int(t)% sec_mod == 0):
            bw=get_bw(t) # watch 1 sec 
            bit=get_bit_type(bw)
            if(bit=='0'):
                print "_ started",t
                started=1
                frames=recv_fr()
                get_msg(frames)

            if(sec_mod!=send_sec_mod): time.sleep(sec_mod-bench_time-1)

def send_fr(frames_bin):
    for b in frames_bin:
        ok=0 # fcs problem reported by recv (111)
        while(not ok):
            a=list(b)
            while(a):
                t=time.time()
                if(int(t)% send_sec_mod == 0):
                    if(int(a.pop(0))): #1
                        time.sleep(0.9)
                    else: #0
                        bw=get_bw(t) # watch 1 sec
                    print '_',t
                    time.sleep(0.9)
            # see if recv sais smth
            count=3
            while(count):
                t=time.time()
                if(int(t)% send_sec_mod == 0):
                    bw=get_bw(t) # watch 1 sec 
                    bit= get_bit_type(bw)
                    print '_ fcs rep',bw,bit
                    if(bit=='0'): ok=0
                    else: ok=1
                    count-=1
                    time.sleep(0.9)
        
                
    
def sender(frames_bin):
    sec_mod=wait_sec_mod
    num0=0; started=0
    while(not started):
        t=time.time()
        if(int(t)% sec_mod == 0):
            bw=get_bw(t) # watch 1 sec 
            print '_',bw
            bit= get_bit_type(bw)
            if(bit=='0'):
                print "_ started",t
                started=1
                send_fr(frames_bin)

            if(sec_mod!=send_sec_mod): time.sleep(sec_mod-bench_time-1)


def construct_frames(inp):
    frames_bin=[]
    f=open(inp,'r')
    content=''.join(f.readlines())
    frames_ascii=[content[i:i+frame_len] for i in range(0,len(content),frame_len)]
    
    pp(frames_ascii)
    for f in frames_ascii: print '_ ',f
    
    for fr in frames_ascii:
        if(len(fr)<frame_len):
            fr=fr+'0'*(frame_len-len(fr))
        fr_bin=''
        for ch in fr:
            ch_bin=bin(ord(ch))[2:] 
            fr_bin+='0'*(ch_len-len(ch_bin))+ch_bin #ensure it is 7 bits len
        frames_bin.append(fr_bin)
    
    frames_fcs_bin=[]
    for fr in frames_bin:
        fcs_bin=bin(sum(int(x) for x in list(fr)))[2:]
        fcs_bin='0'*(fcs_len-len(fcs_bin))+fcs_bin
        frames_fcs_bin.append(fr+fcs_bin)
        
    for f in frames_fcs_bin: print '_ ',f
    return frames_fcs_bin
    

def main():

    usage="Usage: \n"+ sys.argv[0]+" s|d max_for_0 min_for_1 srv_ip srv_port (max_for_0 could be > min_for_1)\n"+ sys.argv[0]+" bench num_times srv_ip srv_port\n"
    if(len(sys.argv)<5): 
        print usage; sys.exit()
    

    if(sys.argv[1]=='bench'):
        globals()['ncat_srv']=sys.argv[3]
        globals()['ncat_srv_port']=int(sys.argv[4])
        bench(int(sys.argv[2])) 
        

    if(len(sys.argv)<5):
        print usage; sys.exit()
    globals()['bw_max_0']=int(sys.argv[2])
    globals()['bw_min_1']=int(sys.argv[3])
    globals()['ncat_srv']=sys.argv[4]
    globals()['ncat_srv_port']=int(sys.argv[5])

    if(sys.argv[1]=='s'): 
        frames_bin=construct_frames(inp)
        pp(frames_bin)
        sender(frames_bin)
    if(sys.argv[1]=='d'): receiver()        

if __name__=="__main__": main()