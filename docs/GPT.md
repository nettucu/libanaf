# libANAF Project GPT specs

This document describes the requirements for a python library and application which deals with ANAF e-factura

## Relevant documents for the project

- [Procedura de inregistrare a aplicaties in ANAF OAUTH](https://static.anaf.ro/static/10/Anaf/Informatii_R/API/Oauth_procedura_inregistrare_aplicatii_portal_ANAF.pdf)
- [Efactura API](https://mfinante.gov.ro/static/10/eFactura/prezentare%20api%20efactura.pdf)
- [Informații tehnice](https://mfinante.gov.ro/ro/web/efactura/informatii-tehnice)

## Other similar projects
- [E-factura by letconex](https://github.com/letconex/E-factura) - Javscript not really working
- [RO E-FACTURA ANAF](https://github.com/Rebootcodesoft/efactura_anaf) - PHP, seems to be quite good
-

## General project requirements

- Python project management is done with poetry to manage required libraries
- Python version supported is version 3.11 and later
- Git will be used to manage the source code
- Path management needs to be done using the pathlib library
- The code must be modern python code, where all function arguments are annotated
- For the command line application typer library will be used
- All functions must be commented
- All function arguments must be english words
- The command line application is to be seperated from the main libanaf library
- The library which does the communication with ANAF servers should not have dependencies with the main application; the main application will use the library to make calls and receive the results for further processing
- The application code will be instrumented with debugging and informational messages using the logging framework
- To configure the logging framework a json file needs to be used conf/logging_py.json
- For output the rich library will be used, however it will not be used to directly output logging messages, instead logging library will be used, unless special console output is required
- Application configuration you must use configuration files stored in a conf/ directory beneath the main application folder
- The configuration files will use TOML format, however you have to use envtoml to read the files so that enviroment variables will be interpolated
- The configuration should be done using a singleton class to make sure it is only read / created once per application
- libanaf must be a separate module from the main application and it should have no dependencies on the
application configuration, it must expose an API which could be used by other applications, either through
function parameters or through environment variables
- the application should have as common parameter the verbosity level and logging needs to be setup based on that
- The project uses secrets as per above document (ANAF OAUTH), the security of secrets is important. They should be stored securely under the main project directory in secrets/ subfolder and an .env file read with dotenv library
- The directory structure should contain a bin/ directory which will call the rest of the application
  the main app binary in this directory should be minimal, it should not be the main typer application object
- The application must also create logs under logs/ directory and the configuration of the logging framework must be done with json file stored in conf/logging_py.json as well as console logging via RichHandler, however the logging should be done with the logging framework and the Rich logging is to be done by the configuration
- libanaf must be a separate module from the main application and it should have no dependencies on the
application configuration, it must expose an API which could be used by other applications, either through
function parameters or through environment variables
- The application/library should raise errors when network communication is not possible or errors are returned from the ANAF API
- The project should use extensive testing
- httpx library will be used to make web requests
- authlib will be used for OAUTH specific

## 1st Feature - Authorization

- This feature should be part of the main ANAF library
- It requires the use of a web server listening for the callback url on port 8000 on the registered callback URL [https://localhost:8000/callback](https://localhost:8000/callback)
- The request for the ANAF authentication API follows the specification in the document "Procedura de inregistrare a aplicaties in ANAF OAUTH"
- The http server should listen to a https endpoint (using self signed certificate), use of ssl should be configurable


Let's generate the application; first the proposed directory structure then the code

---

Next step is to implement the necessary steps to get the list of available invoices from the API, 3. a) in the document "prezentare api efactura.pdf"

* It should use the api supplied by ***api.anaf.ro/prod/***
* It should be a typer command in the application called list-invoices
* The command should take three parameters:
    - the number of days (zile={val1}); default value 60
    - cif (cif={val2}) which should be a number, default value 19507820
    - filter (filtru={val3}) which should be an enum with values E, T, P, R ; default value P
* the help of the command must include the details about the expected parameters:
    val1 = numărul de zile pentru care se face interogarea, format numeric, valorile acceptate de la 1 la 60
    val2 = cif-ul (numeric) pentru care se doreste sa se obtina lista de mesaje disponibile
    val3 = parametru folosit pentru filtrarea mesajelor. Nu este obligatoriu. Valorile acceptate sunt:
    E = ERORI FACTURA
    T = FACTURA TRIMISA
    P = FACTURA PRIMITA
    R = MESAJ CUMPARATOR PRIMIT / MESAJ CUMPARATOR TRANSMIS
e) The request must use the authentication token in the Authorization header:
    It should use the method get_client from LibANAF_AuthClient to return the httpx client
    Authorization: Bearer <TOKEN>
    where <TOKEN> is from the configuration section connection and is named access_token
f) The response is a json list in the following format:
  ```{
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
  ```

  - data_creare is of type date but it is in milliseconds since unix epoch time
  - from detalii the values of id_incarcare and cif_emitent must be taken out
  - if there is a field called "eroare" instead of "mesaje" then that means an error occured and that is the error message

g) Parameters must always be in english language

h) For start I want you to print a table from the received json with the following columns using rich library:
   Data_creare Id_solicitare id_incarcare  cif_emitent  tip id

i) Getting the response from the server must be separated from the display of the list of invoices

Please write the code for the above

---

Next steps are:
1. Download the missing invoices and store the files locally in a directory read from the configuration file
2. For each file, which is a zip file:
   1. unpack from the zip file the invoice XML file
   2. use a different service to convert the XML to PDF which is to be stored in the same location

1. Download the missing invoices and store the files locally in a directory read from the configuration file
  a) The request to download files is <https://api.anaf.ro/prod/FCTEL/rest/descarcare?id={val1}>
    where id is the same id from the previous point
  b) The received IDs should be checked against files downloded to the target directory and only invoices
  not already downloaded should be downloaded
  c) I want you to use Async https clients to download the files (maximum 5 at the same time)
  and I want a progress to display the following information:
    how many invoices i have downloaded from all the invoices i should download, e.g. 2/20 Invoices which needs to be updated as the download progresses
    For each download, using rich display a progress bar of the download (id_invoices .... progress bar)
