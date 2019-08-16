from .imports import *

#Telegram class - creates telegram structure and pack data
class Telegram(Struct):
    
    #packing flags for "telegram_format":
    #<little endial
    #>big endian
    #x - pad byte
    #c - char
    #h - signed int 2 bytes
    #H - unigned int 2 bytes
    #i - signed int 4 bytes
    #I - unigned int 4 bytes
    #i - signed 4 bytes integer
    #I - unigned 4 bytes integer
    #l - signed 8 bytes integer
    #L - unigned 8 bytes integer
    #f - floating point 4 bytes
    #d - floating point 8 bytes
    #Ns - string, N chars
    #P -  void *
    
    def __init__(self,telegram_format,telegram_name,telegram_data_names=None,telegram_data=None,comm_module=None,string_encoding="utf-8"):
        super().__init__(telegram_format)

        #calculate numbers elements in telegram taken from telegram format
        telegram_format_cut = re.sub('[\d<>x=1@]', '', telegram_format)
        
        #set general parameters
        self.string_encoding = string_encoding #default string encoding
        self.len_val = len(telegram_format_cut)
        self.name = telegram_name
        self.len_bytes = super().size
        self.telegram_name = telegram_name
        
        #binding communication_module
        self.comm_module = comm_module #CommModuleSocketTcp class
        if not self.comm_module:
            logging.warning("Telegram %s: no communication module set",telegram_name)
            
        #length check
        if self.len_val == 0:
            raise ValueError("No elements in telegram")
        
        #create nametuple element - data container with parameter access to each element
        try:
            if not telegram_data_names: 
                telegram_data_names = " ".join(list(["v"+str(v) for v in range(self.len_val)]))
            TelegramData = recordclass(telegram_name, telegram_data_names) 
            
        except TypeError:
            raise TypeError("Telegram parameter's string should be 'names' devided by spaces, or empty\(0-n index access\)")
        
        #data check: if no initial data - create: b'' for 's' and 0 for rest of formats
        if not telegram_data:
            telegram_data = [ b'' if k in 'sc' else 0  for k in telegram_format_cut]
            
        self.data = TelegramData._make(telegram_data) 
        
        logging.info("Telegram %s: with format: %s; and variables: %s  - created",telegram_name,telegram_format,telegram_data_names)

    def get_data(self,source_direction) -> "data message": 
        #Doing something to get data
        #in progress
        data = "get data message"
        return data
    def set_string_value(self,value_name,value):
        self.data[value_name] = bytes(value,encoding=self.string_encoding)
        
    def get_string_value(self,value_name,encoding=None):
        if not encoding:
            encoding = self.string_encoding
        return self.data[value_name].decode(encoding)   

    
    def telegram_pack(self):
        binary_data = None
        try:
            #data = map(self.data._asdict().values())
            binary_data = self.pack(*self.data._asdict().values())
        except Exception as ex:
            logging.warning("Telegram %s: _telegram_pack: could not pack telegram: %s",self.telegram_name,ex.args)
        return binary_data
    
    def telegram_unpack(self,binary_data):
        output = None
        try:
            self.data = self.data._make(self.unpack(binary_data))
        except Exception as ex:
            logging.warning("Telegram %s: _telegram_unpack: could not unpack telegram: %s",self.telegram_name,ex.args)
        return output