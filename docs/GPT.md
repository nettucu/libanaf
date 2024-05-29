# libANAF Project GPT specs

You are a python developer tasked with implementing a command line application with the following specs:

- The project name is libanaf
- For the management of the project you have to use poetry, to generate dependencies and
manage other libraries, python version 3.11 and later
- The project will be managed via git for source code
- For the commands interface you must use typer library
- All path related actions should be done using the pathlib library
- All python arguments and type must be fully annotated, including the parameters passed to typer
- All functions must have comments
- The project uses secrets as per above document, as such you must manage the security of such secrets.
They should be stored securely under the main project directory in secrets/ subfolder
- The directory structure should contain a bin/ directory which will call the rest of the application
  the main app binary in this directory should be minimal, it should not be the main typer application object
- For the configuration of the application you must use configuration files stored in a conf/ directory
for the configuration files of the application you must use TOML files/libraries specifically envtoml
so that environment variables are also parsed
- The configuration should be done using a singleton class to make sure it is only read / created once
per application
- The application will use rich library for it's console output, however the logger library will be used
to make the output and pass extra parameters such as extra={"markup": True} to the log function
- The application must create logs under logs/ directory and the configuration of the logging framework must be done with json file stored in conf/logging_py.json as well as console logging via RichHandler, however the logging should be done with the logging framework and the Rich logging is to be done by the configuration
- libanaf must be a separate module from the main application and it should have no dependencies on the
application configuration, it must expose an API which could be used by other applications, either through
function parameters or through environment variables

- the application should have as common parameter the verbosity level and logging needs to be setup based on that

- first application command is "auth" and it needs to authenticate to ANAF portal and retrieve the
authentication token and refresh token, probably rauth library could be used, however here is the quirk:
  a) the auth_url must be open in a browser window with the corect request reason being that the authentication is done externally with a digital certificate (it is similar to how clasp authorizez for google cloud)


Let's generate the application; first the proposed directory structure then the code

================

Next step is to implement the necessary steps to get the list of available invoices from the API, 3. a) in the document prezentare api efactura.pdf

a) It should use the api supplied by *api.anaf.ro/prod/*
b) It should be a typer command in the application called list-invoices
c) The command should take three parameters: 
    - the number of days (zile={val1}); default value 60
    - cif (cif={val2}) which should be a number, default value 19507820
    - filter (filtru={val3}) which should be an enum with values E, T, P, R ; default value P
d) the help of the command must include the details about the expected parameters:
    val1 = numărul de zile pentru care se face interogarea, format numeric, valorile acceptate de la 1 la 60
    val2 = cif-ul (numeric) pentru care se doreste sa se obtina lista de mesaje disponibile
    val3 = parametru folosit pentru filtrarea mesajelor. Nu este obligatoriu. Valorile acceptate sunt:
    E = ERORI FACTURA
    T = FACTURA TRIMISA
    P = FACTURA PRIMITA
    R = MESAJ CUMPARATOR PRIMIT / MESAJ CUMPARATOR TRANSMIS
e) The request must use the authentication token in the Authorization header:
    Authorization: Bearer <TOKEN>
    where <TOKEN> is from the configuration section connection and is named access_token
f) The response is a json list in the following format:
  {
    "mesaje": [
        {
            "data_creare": "202403290821",
            "cif": "19507820",
            "id_solicitare": "4225290319",
            "detalii": "Factura cu id_incarcare=4225290319 emisa de cif_emitent=8939059 pentru cif_beneficiar=19507820",
            "tip": "FACTURA PRIMITA",
            "id": "3347056845"
        },
        ....
    ],
    "serial": "2210701e50c923c412717453",
    "cui": "19507820,2760526082419",
    "titlu": "Lista Mesaje disponibile din ultimele 60 zile"
  }
  - data_creare is of type date but it is in milliseconds since unix epoch time
  - from detalii I need you to extract the value of id_incarcare and cif_emitent
  - if there is a field called "eroare" instead of "mesaje" then that means an error occured and that is the error message

g) Parameters must always be in english language

h) For start I want you to print a table from the received json with the following columns using rich library:
   Data_creare Id_solicitare id_incarcare  cif_emitent  tip id

Please write the code for the above