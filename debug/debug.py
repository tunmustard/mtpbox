import matplotlib.pyplot as plt

class Debug():
    class Image():
        def __init__(self,image,label=""):
            self.image = image
            self.label = label
    
    def show_images_list(image_list,col_number = 2, height = 6):
        row = -(-len(image_list)//col_number) 
        fig = plt.figure(figsize=(15, row*height))
        count = 1
        for img in image_list:
            a = fig.add_subplot(row , col_number, count)
            if img.label:
                a.set_title(img.label)
            plt.imshow(img.image) 
            count=count+1

#Example: debug_img_list.append(Debug.Image(img,"label"))
#Example: Debug.show_images_list(debug_img_list, col_number = 3, height = 5)