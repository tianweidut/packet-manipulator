#!/usr/bin/env python                                                                        
# -*- coding: utf-8 -*-                                                                      
# Copyright (C) 2008 Adriano Monteiro Marques                                                
#                                                                                            
# Author: Francesco Piccinno <stack.box@gmail.com>                                           
#                                                                                            
# This program is free software; you can redistribute it and/or modify                       
# it under the terms of the GNU General Public License as published by                       
# the Free Software Foundation; either version 2 of the License, or                          
# (at your option) any later version.                                                        
#                                                                                            
# This program is distributed in the hope that it will be useful,                            
# but WITHOUT ANY WARRANTY; without even the implied warranty of                             
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the                              
# GNU General Public License for more details.                                               
#                                                                                            
# You should have received a copy of the GNU General Public License                          
# along with this program; if not, write to the Free Software                                
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA 

from __future__ import with_statement

import os
import time
import threading

from scapy import *
from umitCore.I18N import _

__original_write = os.write

def __new_write(fd, txt):
    if fd == 1:
        sys.stdout.write(txt)
    else:
        __original_write(fd, txt)

os.write = __new_write

conf.color_theme = NoTheme()

def load_scapy_protocols():
    import __builtin__
    all = __builtin__.__dict__.copy()
    all.update(globals())
    objlst = filter(lambda (n,o): isinstance(o,type) and issubclass(o,Packet), all.items())
    objlst.sort(lambda x,y:cmp(x[0],y[0]))

    ret = []

    for n,o in objlst:
        ret.append(o)

    return ret

gprotos = load_scapy_protocols()

def get_protocols():
    return gprotos

def get_proto_class_name(protok):
    if not protok.name or protok.name == "":
        return protok.__name__

    return protok.name

def get_proto_name(proto_inst):
    return get_proto_class_name(proto_inst)

def get_proto(proto_name):
    for proto in gprotos:
        if proto.name == proto_name:
            return proto
        if proto.__name__ == proto_name:
            return proto

    print "Protocol named %s not found." % proto_name
    return None

def get_proto_layer(proto):
    return None


def get_packet_raw(metapack):
    if metapack.root:
        return str(metapack.root)
    else:
        return ""

def get_proto_fields(proto_inst):
    if isinstance(proto_inst, type) and isinstance(proto_inst, Packet):
        for f in proto_inst.fields_desc:
            yield f

    elif isinstance(proto_inst, Packet):
        for f in proto_inst.fields_desc:
            yield f

        if not isinstance(proto_inst.payload, NoPayload):
            get_proto_fields(proto_inst.payload)

def get_field_desc(field):
    if not field:
        return _('No description')

    return field.__class__.__name__

def get_packet_protos(metapack):
    if not metapack.root:
        raise StopIteration

    obj = metapack.root

    while isinstance(obj, Packet):
        yield obj

        if not isinstance(obj.payload, NoPayload):
            obj = obj.payload
        else:
            raise StopIteration

class MetaPacket:
    def __init__(self, proto=None):
        self.root = proto

    def include(self, proto):
        if self.root:
            self.root = self.root / proto
        else:
            self.root = proto

    def get_size(self):
        return len(str(self.root))

    def summary(self):
        return self.root.summary()
        ret = ""
        for r in self.root:
            ret += self.root._elt2sum(r)
        return ret

    def get_time(self):
        #self.root.time
        return self.root.sprintf("%.time%")

    def get_source(self):
        ip = self.root.sprintf("{IP:%IP.src%}")
        hw = self.root.sprintf("{Ether:%Ether.src%}")

        if ip:
            return ip

        if hw:
            return hw

        return "N/A"

    def get_dest(self):
        ip = self.root.sprintf("{IP:%IP.dst%}")
        hw = self.root.sprintf("{Ether:%Ether.dst%}")

        if ip:
            return ip

        if hw:
            return hw

        return "N/A"

    def get_protocol_str(self):
        proto = self.root

        while isinstance(proto, Packet):
            if isinstance(proto.payload, NoPayload) or \
               isinstance(proto.payload, Raw):
                return proto.name

            proto = proto.payload


print ">>> %d protocols registered." % len(gprotos)


# Fields section

def get_field_name(field):
    return field.name

def get_field_value(proto, field):
    return getattr(proto, field.name)

def set_field_value(proto, field, value):
    return setattr(proto, field.name, value)

def get_field_value_repr(proto, field):
    return field.i2repr(proto, getattr(proto, field.name))

def get_field_size(proto, field):
    if isinstance(field, StrField):
        # We have to manage in a different way the StrField
        return len(field.i2m(proto, getattr(proto, field.name))) * 8

    if hasattr(field, 'size'):
        return field.size
    else:
        return field.sz * 8

def get_field_offset(packet, proto, field):
    bits = 0
    
    child = packet.root

    while not isinstance(child, NoPayload):
        for f in child.fields_desc:
            if field == f:
                return bits

            bits += get_field_size(child, f)

        child = child.payload

    return bits

def get_field_enumeration_s2i(field):
    return field.s2i.items()

def get_field_enumeration_i2s(field):
    return field.i2s.items()

def set_keyflag_value(proto, flag, key, value):
    if value == get_keyflag_value(proto, flag, key):
        return
    else:
        ret = get_field_value_repr(proto, flag)
        
        if flag.multi:
            if value:
                ret += "+" + key
            else:
                ret = ret.replace(key, "").replace("++", "+")

            if ret and ret[0] == '+':
                ret = ret[1:]
            if ret and ret[-1] == '+':
                ret = ret[:len(ret)-1]

            set_field_value(proto, flag, ret)
        else:
            if value:
                set_field_value(proto, flag, "%s%s" % (ret, key))
            else:
                set_field_value(proto, flag, ret.replace(key, ""))


def get_keyflag_value(proto, flag, key):
    return key in get_field_value_repr(proto, flag)

def is_field_autofilled(field):
    # If the field is setted to None it's calculated
    # automatically
    return field.default == None

def get_flag_keys(field):
    assert isinstance(field, FlagsField)

    if field.multi:
        return map(lambda x: x[0], field.names)
    else:
        return list(field.names)

# Checking stuff

def is_field(field):
    if isinstance(field, Emph):
        return True

    return isinstance(field, Field)

def is_flags(field):
    return isinstance(field, FlagsField)

def is_proto(proto):
    return isinstance(proto, Packet)

def implements(obj, klass):
    if isinstance(obj, Emph):
        return isinstance(obj.fld, klass)

    return isinstance(obj, klass)

# Sniff stuff

from datetime import datetime
from threading import Thread, Lock

from Backend import VirtualIFace
from Backend import BaseSendContext, BaseSniffContext, BaseSendReceiveContext, BaseStaticContext

class StaticContext(BaseStaticContext):
    def load(self):
        if not self.cap_file:
            return False

        data = rdpcap(self.cap_file)

        self.data = []
        for packet in data:
            self.data.append(MetaPacket(packet))

        self.summary = _('%d packets loaded.') % len(data)
        return True

    def save(self):
        if getattr(self, 'get_all_data', False):
            data = self.get_all_data()
        else:
            data = self.get_data()

        if not self.cap_file and not data:
            return False

        data = [packet.root for packet in data]
        wrpcap(self.cap_file, data, gz=('gz' in self.cap_file) and (1) or (0))

        self.summary = _('%d packets written.') % len(data)
        return True

class SendContext(BaseSendContext):
    def __init__(self, metapacket, count, inter, callback, udata=None):
        BaseSendContext.__init__(self, metapacket, count, inter, callback, udata)
        self.thread = None
        self.internal = False

    def _start(self):
        if self.tot_count - self.count > 0:
            self.state = self.RUNNING
            self.internal = True
            self.thread = send_packet(self.packet, self.tot_count - self.count, self.inter, \
                                      self.__send_callback, self.udata)
            return True

        return False

    def _resume(self):
        if self.thread and self.thread.isAlive():
            return False

        return self._start()
    
    def _restart(self):
        if self.thread and self.thread.isAlive():
            return False

        self.count = 0
        return self._start()

    def _stop(self):
        self.internal = False
        return True

    _pause = _stop

    def __send_callback(self, packet, udata):
        if packet:
            self.count += 1
        else:
            self.state = self.NOT_RUNNING

        if self.count == self.tot_count:
            self.summary = "%d packet(s) sent." % self.tot_count
        else:
            self.summary = "Sending packet %d of %d" % (self.count, self.tot_count)

        self.percentage = float(self.count) / float(self.tot_count) * 100.0

        if self.callback:
            self.callback(packet, udata)

        if not self.internal:
            self.state = self.NOT_RUNNING

        return self.state == self.NOT_RUNNING or \
               self.state == self.PAUSED

    #def pause(self):
    #    BaseSendContext.pause(self)
    #    self.thread.join()

    #def stop(self):
    #    BaseSendContext.stop(self)
    #    self.thread.join()

    def join(self):
        self.thread.join()
        self.running = False

class SendReceiveContext(BaseSendReceiveContext):
    def __init__(self, metapacket, count, inter, iface, \
                 scallback, rcallback, sudata=None, rudata=None):

        BaseSendReceiveContext.__init__(self, metapacket, count,
                                        inter, iface, scallback,
                                        rcallback, sudata, rudata)

        self.lock = Lock()
        self.sthread, self.rthread = None, None
        self.internal = False

    def get_all_data(self):
        with self.lock:
            return BaseSendReceiveContext.get_all_data(self)

    def get_data(self):
        with self.lock:
            return BaseSendReceiveContext.get_data(self)

    def set_data(self, val):
        with self.lock:
            self.data = val

    def __threads_active(self):
        if self.sthread and self.sthread.isAlive():
            return True
        if self.rthread and self.rthread.isAlive():
            return True
        return False

    def _start(self):
        if self.tot_count - self.count > 0 and self.remaining > 0:
            self.internal = True
            self.state = self.RUNNING
            self.sthread, self.rthread = send_receive_packet( \
                                self.packet, self.tot_count - self.count, self.inter, \
                                self.iface, self.__send_callback, self.__recv_callback, \
                                self.sudata, self.rudata)
            return True
        return False

    def _resume(self):
        if self.__threads_active():
            return False

        return self._start()
    
    def _restart(self):
        if self.__threads_active():
            return False

        self.count = 0
        self.percentage = 0.0
        self.remaining = self.tot_count
        self.answers = 0
        self.received = 0

        return self._start()

    def _stop(self):
        self.internal = False
        return True

    _pause = _stop

    def get_percentage(self):
        if self.state == self.NOT_RUNNING:
            return 100.0
        else:
            return None

    def __send_callback(self, packet, idx, udata):
        self.count += 1

        self.summary = _('Sending packet %d of %d') % (self.count, self.tot_count)
        self.percentage = (self.percentage + 536870911) % 2147483647

        if self.scallback:
            self.scallback(packet, self.count, udata)

        if not self.internal:
            self.state = self.NOT_RUNNING

        return self.state == self.NOT_RUNNING or \
               self.state == self.PAUSED

    def __recv_callback(self, packet, is_reply, udata):
        if not packet:
            self.internal = False
            self.summary = _('%d of %d replie(s) received') % (self.answers, self.received)
        else:
            self.received += 1
            self.summary = _('Received/Answered/Remaining %d/%d/%d') % (self.received, self.answers, self.remaining)

            if is_reply:
                self.answers += 1
                self.remaining -= 1
                self.data.append(packet)

        self.percentage = (self.percentage + 536870911) % 2147483647

        if self.rcallback:
            self.rcallback(packet, is_reply, udata)

        if not self.internal:
            self.state = self.NOT_RUNNING

        return self.state == self.NOT_RUNNING or \
               self.state == self.PAUSED

    #def pause(self):
    #    BaseSendReceiveContext.pause(self)
    #    self.sthread.join()
    #    self.rthread.join()

    #def stop(self):
    #    BaseSendReceiveContext.stop(self)
    #    self.sthread.join()
    #    self.rthread.join()

    def join(self):
        self.sthread.join()
        self.rthread.join()

        self.running = False

class SniffContext(BaseSniffContext):
    """
    A sniff context for controlling various options.
    """
    has_stop = True
    has_pause = False
    has_restart = True

    def __init__(self, *args, **kwargs):
        BaseSniffContext.__init__(self, *args, **kwargs)

        self.lock = Lock()
        self.prevtime = None
        self.socket = None
        self.internal = True

        self.summary = 'Sniffing on %s' % self.iface
        self.thread = None

    def get_all_data(self):
        with self.lock:
            return BaseSniffContext.get_all_data(self)

    def get_data(self):
        with self.lock:
            return BaseSniffContext.get_data(self)

    def set_data(self, val):
        with self.lock:
            self.data = val

    def get_percentage(self):
        if self.state != self.RUNNING:
            return 100.0
        else:
            if self.stop_count or \
               self.stop_time or \
               self.stop_size:
                return self.percentage
            else:
                return None

    def _start(self):
        self.prevtime = datetime.now()

        if self.iface and not self.socket:
            try:
                self.socket = conf.L2listen(type=ETH_P_ALL, iface=self.iface, filter=self.filter)
            except socket.error, (errno, err):
                self.summary = str(err)
                return False
            except Exception, err:
                self.summary = str(err)
                return False

        self.summary = 'Sniffing on %s' % self.iface
        self.state = self.RUNNING
        self.internal = True
        self.data = []

        self.thread = Thread(target=self.run)
        self.thread.setDaemon(True)
        self.thread.start()

        return True
    
    def _stop(self):
        self.internal = False
        return True

    def _restart(self):
        if self.thread and self.thread.isAlive():
            return False

        # Ok reset the counters and begin a new sniff session
        self.tot_size = 0
        self.tot_time = 0
        self.tot_count = 0

        return self._start()

    def run(self):
        while self.internal:
            packet = self.socket.recv(MTU)

            if not packet:
                continue

            packet = MetaPacket(packet)

            self.tot_count += 1
            self.tot_size += packet.get_size()

            now = datetime.now()
            delta = now - self.prevtime
            self.prevtime = now

            if delta == abs(delta):
                self.tot_time += delta.seconds

            self.data.append(packet)

            if self.callback:
                self.callback(MetaPacket(packet), self.udata)

            lst = []

            if self.stop_count:
                lst.append(float(float(self.tot_count) / float(self.stop_count)))
            if self.stop_time:
                lst.append(float(float(self.tot_time) / float(self.stop_time)))
            if self.stop_size:
                lst.append(float(float(self.tot_size) / float(self.stop_size)))

            if lst:
                self.percentage = float(float(sum(lst)) / float(len(lst))) * 100.0

                if self.percentage >= 100:
                    self.internal = False
            else:
                # ((goject.G_MAXINT / 4) % gobject.G_MAXINT)
                self.percentage = (self.percentage + 536870911) % 2147483647

        self.state = self.NOT_RUNNING
        self.percentage = 100.0
        status = ""

        if self.tot_size >= 1024 ** 3:
            status = "%.1f GB/" % (self.tot_size / (1024.0 ** 3))
        elif self.tot_size >= 1024 ** 2:
            status = "%.1f MB/" % (self.tot_size / (1024.0 ** 2))
        else:
            status = "%.1f KB/" % (self.tot_size / (1024.0))

        if self.tot_time >= 60 ** 2:
            status += "%d h/" % (self.tot_time / (60 ** 2))
        elif self.tot_time >= 60:
            status += "%d m/" % (self.tot_time / 60)
        else:
            status += "%d s/" % (self.tot_time)

        status += "%d pks" % (self.tot_count)

        self.summary = _('Finished sniffing on %s (%s)') % (self.iface, status)

        if self.callback:
            self.callback(None, self.udata)

def find_all_devs():
    ifaces = get_if_list()

    ips = []
    hws = []
    for iface in ifaces:
        ip = "0.0.0.0"
        hw = "00:00:00:00:00:00"
        
        try:
            ip = get_if_addr(iface)
        except Exception:
            pass

        try:
            hw = get_if_hwaddr(iface)
        except Exception:
            pass

        ips.append(ip)
        hws.append(hw)

    ret = []
    for iface, ip, hw in zip(ifaces, ips, hws):
        ret.append(VirtualIFace(iface, hw, ip))

    return ret

# Sending/Receiving

def _send_packet(metapacket, count, inter, callback, udata):
    packet = metapacket.root

    while count > 0:
        send(packet, 0, 0)
        count -= 1

        if callback(metapacket, udata) == True:
            return

        time.sleep(inter)

    callback(None, udata)

def send_packet(metapacket, count, inter, callback, udata=None):
    """
    Send a metapacket in thread context

    @param metapacket the packet to send
    @param count send n count metapackets
    @param inter interval between two consecutive sends
    @param callback a callback to call at each send (of type packet, udata)
           when True is returned the send thread is stopped
    @param udata the userdata to pass to the callback
    """
    send_thread = threading.Thread(target=_send_packet, args=(metapacket, count, inter, callback, udata))
    send_thread.setDaemon(True) # avoids zombies
    send_thread.start()

    return send_thread

def _sndrecv_sthread(wrpipe, socket, packet, count, inter, callback, udata):
    try:
        for idx in xrange(count):
            socket.send(packet)

            if callback(packet, idx, udata):
                break

            time.sleep(inter)
    except SystemExit:
        pass
    except Exception, err:
        print "Error in _sndrecv_sthread(PID: %d EXC: %s)" % (os.getpid(), str(err))
    else:
        cPickle.dump(arp_cache, wrpipe)
        wrpipe.close()

def _sndrecv_rthread(sthread, rdpipe, socket, packet, count, callback, udata):
    ans = 0
    nbrecv = 0
    notans = count

    force_exit = False
    packet_hash = packet.hashret()

    inmask = [socket, rdpipe]

    while True:
        r = None
        if FREEBSD or DARWIN:
            inp, out, err = select(inmask, [], [], 0.05)
            if len(inp) == 0 or socket in inp:
                r = socket.nonblock_recv()
        else:
            inp, out, err = select(inmask, [], [], None)
            if len(inp) == 0:
                return
            if socket in inp:
                r = socket.recv(MTU)
        if r is None:
            continue

        if r.hashret() == packet_hash and r.answers(packet):
            ans += 1

            if notans:
                notans -= 1

            if callback(MetaPacket(r), True, udata):
                force_exit = True
                break
        else:
            nbrecv += 1

            if callback(MetaPacket(r), False, udata):
                force_exit = True
                break

        if notans == 0:
            break
    try:
        ac = cPickle.load(rdpipe)
    except EOFError:
        print "Child died unexpectedly. Packets may have not been sent"
    else:
        arp_cache.update(ac)

    if sthread and sthread.isAlive():
        sthread.join()

    if not force_exit:
        callback(None, False, udata)

def send_receive_packet(metapacket, count, inter, iface, scallback, rcallback, sudata=None, rudata=None):
    """
    Send/receive a metapacket in thread context

    @param metapacket the packet to send
    @param count send n count metapackets
    @param inter interval between two consecutive sends
    @param iface the interface where to wait for replies
    
    @param callback a callback to call at each send (of type packet, packet_idx, udata)
    @param sudata the userdata to pass to the send callback

    @param callback a callback to call at each receive (of type reply_packet, is_reply, received, answers, remaining)
    @param sudata the userdata to pass to the send callback
    """
    packet = metapacket.root

    if not isinstance(packet, Gen):
        packet = SetGen(packet)

    if not count or count <= 0:
        count = 1

    socket = conf.L3socket(iface=iface)

    rdpipe, wrpipe = os.pipe()
    rdpipe = os.fdopen(rdpipe)
    wrpipe = os.fdopen(wrpipe, 'w')

    send_thread = threading.Thread(target=_sndrecv_sthread,
                                   args=(wrpipe, socket, packet, count, inter, scallback, sudata))
    recv_thread = threading.Thread(target=_sndrecv_rthread,
                                   args=(send_thread, rdpipe, socket, packet, count, rcallback, rudata))

    send_thread.setDaemon(True)
    recv_thread.setDaemon(True)

    send_thread.start()
    recv_thread.start()

    return send_thread, recv_thread

# Routes stuff

def route_resync():
    conf.route.resync()

def route_list():
    for net, msk, gw, iface, addr in conf.route.routes:
        yield (ltoa(net), ltoa(msk), gw, iface, addr)

def route_add(self, host, net, gw, dev):
    conf.route.add({'host':host, 'net':net, 'gw':gw, 'dev':dev})

def route_remove(self, host, net, gw, dev):
    conf.route.delt({'host':host, 'net':net, 'gw':gw, 'dev':dev})

PMField             = Field
PMFlagsField        = FlagsField

PMBitField          = None
PMIPField           = IPField
PMByteField         = ByteField
PMShortField        = ShortField
PMLEShortField      = LEShortField
PMIntField          = IntField
PMSignedIntField    = SignedIntField
PMLEIntField        = LEIntField
PMLESignedIntField  = LESignedIntField
PMLongField         = LongField
PMLELongField       = LELongField
PMStrField          = StrField
PMLenField          = LenField
PMRDLenField        = RDLenField
PMFieldLenField     = FieldLenField
PMBCDFloatField     = BCDFloatField
PMBitField          = BitField
PMEnumField         = EnumField
