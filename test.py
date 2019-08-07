import time
import logging
import queue
import threading
import concurrent.futures
from concurrent.futures.thread import ThreadPoolExecutor


#initialization of logging
format = "%(asctime)s: %(message)s"
logging.basicConfig(format=format, level=logging.DEBUG,datefmt="%H:%M:%S")


#Pipeline class for Communicator 
class Pipeline(queue.Queue):
    def __init__(self,buffer_size,client_name,name):
        super().__init__(maxsize=buffer_size)
        self.name = name
        logging.debug("%s's pipeline %s: created",client_name,name)
        ##Status: .full() .empty()
    def __str__(self):
        return "pipeline_"+self.name
        
#Communicator class
class Communicator(object):
    
    def __init__ (self,con_type:str,con_dir:str,buffer_size_out:int,buffer_size_inp:int=0,simulation = False):
        
        self.con_type = con_type
        self.con_dir = con_dir
        self.buffer_size_inp = buffer_size_inp
        self.buffer_size_out = buffer_size_out
        if self.con_dir =="both":
            self.pipeline_inp = Pipeline(buffer_size_inp,con_type,"inp")
            self.pipeline_out = Pipeline(buffer_size_out,con_type,"out")
        elif self.con_dir =="inp":
            self.pipeline_inp = Pipeline(buffer_size_inp,con_type,"inp")
            self.pipeline_out = None
        elif self.con_dir =="out":    
            self.pipeline_inp = None
            self.pipeline_out = Pipeline(buffer_size_out,con_type,"out")
        else:
            raise ValueError("Communication direction must be 'inp'/'out'/'both'")
        #Real communication module, which depends of communication partner and choose proper library
        #TODO
        self.comm_module = object #TODO
        
        #Threading object
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        #theading lock to secure set_data(), get_data() function access
        self.set_data_lock = threading.Lock()
        self.get_data_lock = threading.Lock()
        
        #Theading events to stop/start communication
        self.event_out_start = threading.Event()
        self.event_inp_start = threading.Event()
        
        #Simulation block
        self.simulation = simulation
        self.sim_recv_cnt = 0 #receive counter simulation
        
        logging.info("Communicator %s with %s direction: created",con_type,con_dir)
        
    def __send_data(self,data) -> int:
        logging.debug("Communicator %s: __send_data: preparing for send",self.con_type)
        code_result = 0
        
        if self.simulation:
            time.sleep(2) #Simulation
            code_result = True #Simulation
        else:
            logging.debug("Communicator %s: __send_data: Program stopped TODO",self.con_type)
            raise ValueError("TODO")
            #TODO
        return code_result
    
    def __recieve_data(self) -> (str,int):
        logging.debug("Communicator %s: __recieve_data: preparing for recieve",self.con_type)
        code_result = False
        
        if self.simulation:
            #Recieve data simulation
            data = "Simulated message from PLC #"+str(self.sim_recv_cnt) #Simulation
            self.sim_recv_cnt += 1 #Simulation
            code_result = True #Simulation
            time.sleep(1)
        else:
            logging.debug("Communicator %s: __recieve_data: Program stopped TODO",self.con_type)
            raise ValueError("TODO")
            #TODO
        
        
        return data,code_result
    
    def __get_data_from_buffer(self,pipeline) -> object:
        #logging.debug("Communicator %s: __get_data_from_buffer: trying to get data",self.con_type)
        value = pipeline.get(block=False)
        logging.debug("Communicator %s: __get_data_from_buffer: get data from %s ok",self.con_type,pipeline)
        return value

    def __set_data_to_buffer(self,pipeline,value):
        #logging.debug("Communicator %s: __set_data_to_buffer: trying to set data to %s",self.con_type,pipeline)
        pipeline.put(value,block=False)
        logging.debug("Communicator %s: __set_data_to_buffer: set data ok to %s",self.con_type,pipeline)
    
    def __thread_update_inp_buffer(self,pipeline,run_event):
        k = 0
        logging.debug("Communicator %s: __thread_update_inp_buffer: checking communication event",self.con_type)
        while run_event.is_set():
            logging.debug("Communicator %s: __thread_update_inp_buffer: trying to recieve data",self.con_type)
            data,code_result = self.__recieve_data() 
            #result put to buffer
            if code_result:
                logging.debug("Communicator %s: __thread_update_inp_buffer: recieved data %s",self.con_type,data)
                self.__set_data_to_buffer(pipeline,data)
            else:
                logging.debug("Communicator %s: __thread_update_inp_buffer: no data recieved yet",self.con_type)
        
        logging.info("Communicator %s: __thread_update_inp_buffer: stop communication event",self.con_type)
            
    def __thread_update_out_buffer(self,pipeline,run_event):
        while run_event.is_set():
            _comm_ready = True #TMP
            if _comm_ready and not pipeline.empty():
                logging.debug("Communicator %s: __thread_update_out_buffer: trying to send data",self.con_type)
                code_result = self.__send_data(self.__get_data_from_buffer(pipeline))
                if code_result:
                    logging.debug("Communicator %s: __thread_update_out_buffer: data send ok",self.con_type)
                else:
                    logging.warning("Communicator %s: __thread_update_out_buffer: error sending data",self.con_type)
        logging.info("Communicator %s: __thread_update_out_buffer: stop communication event",self.con_type)
    
    def set_data(self,data) -> True:
        logging.debug("Communicator %s: set_data: trying to add data to %s",self.con_type,self.pipeline_out)
        code_result = False
        #secure operation from multithreading access
        self.set_data_lock.acquire()
        #add data to output buffer
        if not self.pipeline_out.full():
            self.__set_data_to_buffer(self.pipeline_out,data)
            code_result = True
            logging.info("Communicator %s: set_data: add data to %s ok",self.con_type,self.pipeline_out)
        else:
            logging.warning("Communicator %s: set_data: not added, %s is full",self.con_type,self.pipeline_out)
        #release operation for multithreading access
        self.set_data_lock.release()
        return code_result
    
    
    def get_data(self) -> str:
        logging.debug("Communicator %s: get_data: trying to get data from %s",self.con_type,self.pipeline_inp)
        data = None
        code_result = False
        #secure operation from multithreading access
        self.get_data_lock.acquire()
        #get data from inout buffer
        if not self.pipeline_inp.empty():
            data = self.__get_data_from_buffer(self.pipeline_inp)
            code_result = True
            logging.info("Communicator %s: get_data: get data from %s ok: %s",self.con_type,self.pipeline_inp, data)
        else:
            logging.info("Communicator %s: get_data: no data, %s is empty",self.con_type,self.pipeline_inp)
        #release operation for multithreading access
        self.get_data_lock.release()
        return data,code_result
    
    def get_out_buff_count(self) -> int:
        #secure operation from multithreading access
        self.get_data_lock.acquire()
        #get queue size
        result = self.pipeline_out.qsize()
        logging.info("Communicator %s: get_out_buff_count: qsize of %s is %s ",self.con_type,self.pipeline_out,result)
        #release operation for multithreading access
        self.get_data_lock.release()
        return result
    
    def get_inp_buff_count(self) -> int:
        #secure operation from multithreading access
        self.get_data_lock.acquire()
        #get queue size
        result = self.pipeline_inp.qsize()
        logging.info("Communicator %s: get_inp_buff_count: qsize of %s is %s ",self.con_type,self.pipeline_inp,result)
        #release operation for multithreading access
        self.get_data_lock.release()
        return result
    
    def start_communication(self) -> None:
        logging.debug("Communicator %s: start_communication: try to start communication treading",self.con_type)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as self.executor: #self.executor
            #set communication on events
            self.event_inp_start.set() #start inp communication
            self.event_out_start.set() #start out communication
            #this thread updated incoming communication buffer
            self.executor.submit(self.__thread_update_inp_buffer, self.pipeline_inp,self.event_inp_start)  
            #this thread updated outcoming communication buffer
            self.executor.submit(self.__thread_update_out_buffer, self.pipeline_out,self.event_out_start)
        logging.debug("Communicator %s: start_communication: communicagion threading started ok") 
        
        
    def stop_communication(self):
        logging.debug("Communicator %s: start_communication: trying to stop threading")
        self.event_inp_start.clear() #stop inp communication
        self.event_out_start.clear() #stop out communication
        self.executor.shutdown(wait=True)
        logging.debug("Communicator %s: start_communication: threading stopped??")
    
plc_comm =  Communicator("PLC","both",10,10,simulation = True)
#plc_comm.set_data("Message1 to be sent")
#plc_comm.set_data("Message2 to be sent")
#plc_comm.get_out_buff_count()
#plc_comm.get_data()
#plc_comm.get_inp_buff_count()
plc_comm.start_communication()
time.sleep(5)
plc_comm.get_data()