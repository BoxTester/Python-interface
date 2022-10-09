import pymysql

class Mysql(object):

    def __init__(self,host,username,password,database):
        self.host = host
        self.username = username
        self.password = password
        self.database = database
        self.con = pymysql.connect(host=self.host,user=self.username,password=self.password,database=self.database,charset='utf8')
        # self.con = pymysql.connect(self.host,self.username,self.password,self.database,cursorclass=pymysql.cursors.DictCursor,charset='utf8')
        

    def execute(self,sql):
        self.cursor = self.con.cursor()
        try:
            data = self.cursor.execute(sql)
            self.con.commit()
            return data
        except:
            self.con.rollback()
        finally:
            self.close()

    def insert(self,sql):
        self.execute(sql)
            
    def delete(self,sql):
        self.execute(sql)

    def update(self,sql):
        self.execute(sql)

    def select(self,sql,one=True):
        self.cursor = self.con.cursor()
        try:
            self.cursor.execute(sql)
            if one:
                return self.cursor.fetchone()
            else:
                return self.cursor.fetchall()

        except:
            print('Error: unable to fecth data')
        finally:
            self.close()

    def close(self):
        self.cursor.close()
        self.con.close()

if __name__ == "__main__":
    MysqlHost = 'localhost'
    MysqlUsername = 'root'
    MysqlPassword = 'root'
    MysqlDatabase = 'test'

    con = Mysql(MysqlHost,MysqlUsername,MysqlPassword,MysqlDatabase)
    # con = Mysql("localhost","root","root","test")
    # con = pymysql.connect(MysqlHost,MysqlUsername,MysqlPassword,MysqlDatabase,charset='utf8')
    # print(con.select("select * from test"))
    print(con.insert("INSERT INTO `test`.`test`(`id`, `name`, `group`) VALUES ('12', 'ttttt', 'aaaa')"))