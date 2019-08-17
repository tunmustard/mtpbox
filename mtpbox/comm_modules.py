from .imports import *
from concurrent.futures.thread import ThreadPoolExecutor

#static paramenters
TCP_PARTNERS_ALL = "0"

#Class for communication module. Implement 
class CommModuleSocketTcp(object):
    
    def __init__ (self,name,HOST="0.0.0.0",PORT=65432,listen_backlog=5,buffer_size=1024,timeout=0.2,con_dir="both", \
                  main_buff_size_inp=10,main_buff_size_out=10,loc_buff_size_out=10,loc_buff_size_inp=10):
        
        #General parameters
        self.comm_type = "Communication module socket TCP/IP" #static
        self.name = name
        self.con_dir=con_dir #can be "both"/"inp"/"out"
        self.PARTNERS_ALL = TCP_PARTNERS_ALL #partner name to send telegram to all partners
        
        #Socket configuration
        self.HOST = HOST # The server's hostname or IP address
        self.PORT = PORT # The port used by the server
        self.buffer_size = buffer_size
        self.listen_backlog = listen_backlog
        self.timeout=timeout
        
        #Main parameters
        self.partners_filter = []  #Use form eg for :'10.17.35.137.64762' or '10.17.35' or '10.17.35.137.647'
        self.partners = []
        self.partners_dict = {}
        self.message_queues_inp = {}
        self.message_queues_out = {}
        self.loc_buff_size_inp=loc_buff_size_inp
        self.loc_buff_size_out=loc_buff_size_out
        self.all_message_queues_inp = queue.Queue(main_buff_size_inp) #commulative queue for input messages
        self.all_message_queues_out = queue.Queue(main_buff_size_out) #commulative queue for output messages
        
        #Threading parameters
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.event_comm_start = threading.Event()
        
        logging.debug("Communication module %s: created",self.name)
    
    def __str__(self):
        return  self.comm_type+ ":" + self.name
    
    def __thread_run_server(self,run_event):
        logging.debug("Communication module %s: trying to start server",self.name)
        #initialistation of sockets
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setblocking(0)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
            server.bind((self.HOST, self.PORT))
            server.listen(self.listen_backlog)
            logging.debug("Communication module %s: starting server...",self.name)
            #data exchange parameters
            inputs = [server]
            outputs = []
                
            logging.info("Communication module %s: server started",self.name)
            if not self.partners_filter:
                logging.warning("Communication module %s: partners filter is empty. No connections allowed",self.name)
            
            #start server proccess loop
            while run_event.is_set():
                readable, writable, exceptional = select.select(inputs, outputs, inputs,self.timeout)
                #list of connections to be terminated
                connection_terminate_list = []
                #get new data/connection

                for s in readable:
                    #if server recived new connection
                    if s is server:
                        connection, client_address = s.accept()
                        connection.setblocking(0)
                        #represent partner IP.PORT as name
                        connection_name = '.'.join(map(str,connection.getpeername()))
                        logging.info("Communication module %s: incoming partner name %s",self.name,connection_name)
                        #check if connection_name fit the filter XX.XX.XX.XX.XXXXX requirements
                        if any(map(lambda y: re.search("^"+y, connection_name)!=None,self.partners_filter)):
                            logging.info("Communication module %s: partner name %s accepted",self.name,connection_name)
                            #add new event source to the list
                            inputs.append(connection)
                            if connection_name in self.partners_dict:
                                logging.warning("Communication module %s: partner %s reset",self.name,connection_name)                       
                            #add to dictionary partners_dict: connection_name<->connection 
                            self.partners_dict[connection_name]=connection 
                            #create inp/out queue for new connection
                            self.message_queues_inp[connection] = queue.Queue(self.loc_buff_size_inp)
                            self.message_queues_out[connection] = queue.Queue(self.loc_buff_size_out)                   
                        else:
                            logging.warning("Communication module %s: partner name %s rejected",self.name,connection_name)
                            if connection not in connection_terminate_list:
                                connection_terminate_list.append(connection)
                    
                    #if recieved new data from connection
                    else:
                        data = s.recv(self.buffer_size)
                        connection_name = '.'.join(map(str,s.getpeername()))
                        #put to separate queue
                        try:
                            self.message_queues_inp[s].put_nowait(data) 
                        except queue.Full:
                            logging.warning("Communication module %s: connection %s input buffer full, data lost",self.name,connection_name)
                            try:
                                #if buffer is full - erase one element and put again
                                data_lost = self.message_queues_inp[s].get_nowait()
                                self.message_queues_inp[s].put_nowait(data)
                            except queue.Empty:
                                pass 
                        else:
                            #put to main input queue
                            try:
                                self.all_message_queues_inp.put_nowait((connection_name,data)) #put to cumulative queue
                            except queue.Full:
                                logging.warning("Communication module %s: main input buffer full, data lost",self.name)
                                try:
                                    #if buffer is full - erase one element and put again
                                    data_lost = self.all_message_queues_inp.get_nowait()
                                    self.all_message_queues_inp.put_nowait((connection_name,data))
                                except queue.Empty:
                                    pass 
                            else:
                                logging.debug("Communication module %s: connection %s: data recieved",self.name,connection_name)
                        
                        #check if zero message, so, terminate connection
                        if not data:
                            logging.debug("Communication module %s: connection %s: empty message -> XXX disconnecting XXX",self.name,connection_name)
                            if s not in connection_terminate_list:
                                connection_terminate_list.append(s)  
 
                #send data
                for s in writable:
                    try:
                        next_msg = self.message_queues_out[s].get_nowait()
                    except queue.Empty:
                        outputs.remove(s)
                    else:
                        s.send(next_msg)
                        logging.debug("Communication module %s: connection %s: data sent",self.name,connection_name)

                #spread input queue between separate queues
                while True:
                    try:
                        #get data from main output queue, telegram format: (connection_name,data)
                        (conn_name,data) = self.all_message_queues_out.get_nowait() 
                        logging.debug("Communication module %s: checking main output buffer",self.name)
                        #check for specific type of telegram
                        if conn_name==self.PARTNERS_ALL:
                            #send to all
                            for pn,pc in self.partners_dict.items():
                                try:
                                    self.message_queues_out[pc].put_nowait(data)
                                    if pc not in outputs:
                                        outputs.append(pc)
                                except queue.Full:
                                    logging.warning("Communication module %s: connection %s: output buffer full, data lost",self.name,pn)
                        else:    
                            if conn_name in self.partners_dict:
                                logging.debug("Communication module %s: found data for %s",self.name,conn_name)
                                pc = self.partners_dict[conn_name]
                                #send to selected partner
                                try:
                                    self.message_queues_out[pc].put_nowait(data)
                                    if pc not in outputs:
                                        outputs.append(pc)
                                except queue.Full:
                                    logging.warning("Communication module %s: connection %s: output buffer full, data lost",self.name,conn_name)
                    except queue.Empty:  
                        break

                #mark connection to be terminated if socker error
                for s in exceptional:
                    logging.warning("Communication module %s:  error communication with: %s",self.name,'.'.join(map(str,s.getpeername())))   
                    if s not in connection_terminate_list:
                        connection_terminate_list.append(s) 
 
                #mark connection to be terminated which are not in the list partners_dict
                for s in inputs:
                    if  s is not server:
                        if s not in self.partners_dict.values():
                            logging.warning("Communication module %s: connection %s is not allowed anymore",self.name,'.'.join(map(str,s.getpeername()))) 
                            if s not in connection_terminate_list:
                                connection_terminate_list.append(s)
                #terminate connection
                if connection_terminate_list:
                    for s in connection_terminate_list:
                        conn_name = '.'.join(map(str,s.getpeername()))
                        logging.warning("Communication module %s: closing connection %s",self.name,conn_name)
                        
                        if s in inputs:
                            inputs.remove(s)
                        if s in outputs:
                            outputs.remove(s)
                        s.close()
                        #check if connection removed from partner_dict:
                        self.partners_dict = {key:val for key, val in self.partners_dict.items() if val != s}
                        #clean connections queue
                        self.message_queues_inp.pop(s,None)
                        self.message_queues_out.pop(s,None)
                    #reset termination list    
                    connection_terminate_list = []
                    
                #update partners list (readonly):
                self.partners = list(self.partners_dict.keys())
                
            #stopping server: close all active connections:
            for pn,pc in self.partners_dict.items():
                logging.warning("Communication module %s: closing connection %s",self.name,pn)
                pc.close()
                #clean partner_dict:
            self.partners_dict = {}
            #clean connections queue
            self.message_queues_inp = {}
            self.message_queues_out = {}
            
        logging.info("Communication module %s: server stopped",self.name)   
    
    def recieve_data(self,partner=TCP_PARTNERS_ALL):
        if partner==TCP_PARTNERS_ALL:
            try:
                data = self.all_message_queues_inp.get_nowait()
                logging.debug("Communication module %s: recieve_data: data recived from main inp buffer",self.name)
            except queue.Empty:
                logging.debug("Communication module %s: recieve_data: main input buffer empty",self.name)
                data = None 
        else:
            if partner in self.partners_dict: 
                try:
                    data = self.message_queues_inp[self.partners_dict[partner]].get_nowait()
                    logging.debug("Communication module %s: recieve_data: data recived from %s inp buffer",self.name,partner)
                except queue.Empty:
                    logging.debug("Communication module %s: recieve_data: input buffer %s empty",self.name,partner)
                    data = None   
            else:
                logging.debug("Communication module %s: recieve_data: no partner '%s' found",self.name,partner)
                data = None
        return data
        
    def send_data(self,data,partner=TCP_PARTNERS_ALL):
        result = False
        #check partner
        if (partner in self.partners_dict) or (partner==TCP_PARTNERS_ALL):
            try:
                self.all_message_queues_out.put_nowait((partner,data)) 
                result = True
                logging.debug("Communication module %s: send_data: data to '%s' added to main output buffer",self.name,partner)
            except queue.Full:
                logging.warning("Communication module %s: send_data: main %s output buffer full",self.name)
        else:
            logging.warning("Communication module %s: send_data: no partner '%s' found",self.name,partner)
    
    #get communication partners list
    def get_partners(self):
        return self.partners
    
    #remove partner from communication. Remove partner by filter ^0.0.0.0.0000 or ^0.0.0.0 ^0
    def remove_partner(self,partner=TCP_PARTNERS_ALL):
        partners_to_remove = []
        if partner == TCP_PARTNERS_ALL: #delete all partners
            partners_to_remove = list(self.partners_dict.keys())
        else:
            for k,v in self.partners_dict.items():
                if re.search("^"+partner, k):
                    partners_to_remove.append(k)  
                    
        for v in partners_to_remove:
            self.partners_dict.pop(v,None)
            logging.info("Communication module %s: remove_partner: partner '%s' removed from communication list",self.name,v)
    
    #set communication partners filter
    def set_partners_filter(self,partners_filter):
        if(type(partners_filter)==list):
            self.partners_filter = partners_filter
            logging.debug("Communication module %s: set_partners_filter: new partner filter set: %s",self.name,partners_filter)
        else:
            logging.warning("Communication module %s: set_partners_filter: filter not accepted, list required",self.name)
    
    #start communication function
    def start_communication(self) -> None:
        logging.debug("Communication module %s: start_communication: try to start communication treading",self.name)
        #with executor as executor: #self.executor
        #set communication on events
        self.event_comm_start.set() #start communication flag
        #start thread with socket server
        self.executor.submit(self.__thread_run_server,self.event_comm_start)  
        logging.debug("Communication module %s: start_communication: communication threading started ok",self.name)
    
    #stop communication function
    def stop_communication(self):
        logging.debug("Communication module %s: stop_communication: trying to stop threading",self.name)
        self.event_comm_start.clear() #stop communication flag
        self.executor.shutdown(wait=True)
        logging.debug("Communication module %s: stop_communication: threading stopped",self.name)
    def is_data(self,partner=TCP_PARTNERS_ALL):
        result = False
        if partner==TCP_PARTNERS_ALL:
            #TODO: change to: for in partners_dict?????
            result = self.all_message_queues_inp.qsize()>0
        else:
            if partner in self.partners_dict:
                result = self.message_queues_inp[self.partners_dict[partner]].qsize()>0
            else:
                logging.debug("Communication module %s: is_data: no partner '%s' found",self.name,partner)
        return result
    