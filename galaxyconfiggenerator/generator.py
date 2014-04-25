# encoding: utf-8
'''
@author:     delagarza

'''

import string
import sys
import os
import traceback

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
from CTDopts.CTDopts import CTDModel, _InFile, _OutFile, ParameterGroup, _Choices, _NumericRange, _FileFormat, ModelError

from xml.dom.minidom import Document
from string import strip

__all__ = []
__version__ = 0.1
__date__ = '2014-03-26'
__updated__ = '2014-03-26'

TYPE_TO_GALAXY_TYPE = {int: 'integer', float: 'float', str: 'text', bool: 'boolean', _InFile: 'data', 
                       _OutFile: 'data', _Choices: 'select'}

class CLIError(Exception):
    '''Generic exception to raise and log different fatal errors.'''
    def __init__(self, msg):
        super(CLIError).__init__(type(self))
        self.msg = "E: %s" % msg
    def __str__(self):
        return self.msg
    def __unicode__(self):
        return self.msg

def main(argv=None): # IGNORE:C0111
    '''Command line options.'''

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_name = os.path.basename(sys.argv[0])
    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_shortdesc = "GalaxyConfigGenerator - A project from the GenericWorkflowNodes family (https://github.com/orgs/genericworkflownodes)"
    program_usage = '''
    USAGE:
    
    Parse a single CTD file and generate a Galaxy wrapper:
    $ python generator.py -i input.ctd -o output.xml
    
    Parse all found CTD files (files with .ctd and .xml extension) in a given folder and output converted Galaxy wrappers in a given folder:
    $ python generator.py --input-directory /home/johndoe/ctds --output-directory /home/johndoe/galaxywrappers
    '''
    program_license = '''%(shortdesc)s
    Copyright 2014, Luis de la Garza

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
    
    %(usage)s
''' % {'shortdesc':program_shortdesc, 'usage':program_usage}

    

    try:
        # Setup argument parser
        parser = ArgumentParser(description=program_license, formatter_class=RawDescriptionHelpFormatter, add_help=True)
        parser.add_argument("-i", "--input-file", dest="input_file", help="provide a single input CTD file to convert", required=True)
        parser.add_argument("-o", "--output-file", dest="output_file", help="provide a single output Galaxy wrapper file", required=True)
        # verbosity will be added later on, will not waste time on this now
        # parser.add_argument("-v", "--verbose", dest="verbose", action="count", help="set verbosity level [default: %(default)s]")
        parser.add_argument("-V", "--version", action='version', version=program_version_message)
        
        # Process arguments
        args = parser.parse_args()
        
        # collect arguments
        input_file = args.input_file
        output_file = args.output_file
        
        #if verbose > 0:
        #    print("Verbose mode on")
        convert(input_file, output_file)
        return 0

    except KeyboardInterrupt:
        ### handle keyboard interrupt ###
        return 0
    except IOError, e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "Could not access input file [%(input)s] or output file [%(output)s]\n" % {"input":input_file, "output":output_file})
        sys.stderr.write(indent + "For help use --help\n")
        # #define EX_NOINPUT      66      /* cannot open input */
        return 66
    except ModelError, e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "There seems to be a problem with your input CTD [%s], please make sure that it is a valid CTD.\n" % input_file)
        sys.stderr.write(indent + "For help use --help\n")
        return 1
    except Exception, e:
        traceback.print_exc()
        return 2
    
def convert(input_file, output_file):
    # first, generate a model
    print("Parsing CTD from [%s]" % input_file)
    model = CTDModel(from_file=input_file)
    
    doc = Document()
    tool = create_tool(doc, model)
    doc.appendChild(tool)
    create_description(doc, tool, model)
    create_requirements(doc, tool, model)
    create_command(doc, tool, model)
    create_inputs(doc, tool, model)
    create_outputs(doc, tool, model)
    create_help(doc, tool, model)
    
    # finally, serialize the tool
    doc.writexml(open(output_file, 'w'), indent="    ", addindent="    ", newl='\n')
    print("Generated Galaxy wrapper in [%s]\n" % output_file)    
    
def create_tool(doc, model):
    tool = doc.createElement("tool")
    # use the same name of the tool... maybe a future version would contain a way to add a specific ID?
    tool.setAttribute("id", model.name)
    tool.setAttribute("version", model.version)
    tool.setAttribute("name", model.name)
    return tool

def create_description(doc, tool, model):
    if "description" in model.opt_attribs.keys() and model.opt_attribs["description"] is not None:
        description_node = doc.createElement("description")
        description = doc.createTextNode(model.opt_attribs["description"])
        description_node.appendChild(description)
        tool.appendChild(description_node)

def create_requirements(doc, tool, model):
    #TODO: how to pass requirements? command line? included in CTD? 
    pass

def create_command(doc, tool, model):
    command = get_tool_executable_path(model) + ' '
    for param in extract_parameters(model):
        # for boolean types, we only need the placeholder
        if param.type is not bool:
            # add the parameter name
            command += '-' + param.name + ' '
        # we need to add the placeholder
        command += "$" + get_galaxy_parameter_name(param.name) + ' '
            
    command_node = doc.createElement("command")
    command_text_node = doc.createTextNode(command.strip())
    command_node.appendChild(command_text_node)
    tool.appendChild(command_node)
    

def get_tool_executable_path(model):
    # rules to build the galaxy executable path:
    # if executablePath is null and executableName is null, then the name of the tool will be used
    # if executablePath is null and executableName is not null, then executableName will be used
    # if executablePath is not null and executableName is null, then executablePaht and the name of the tool will be used
    # if executablePath is not null and executableName is not null, then both will be used
    command = None
    # first, check if the model has executablePath / executableName defined
    executablePath = model.opt_attribs.get("executablePath", None)
    executableName = model.opt_attribs.get("executableName", None)
    # fix the executablePath to make sure that there is a '/' in the end
    if executablePath is not None:
        executablePath = executablePath.strip()
        if not executablePath.endswith('/'):
            executablePath += '/'
        
    if executablePath is None:
        if executableName is None:
            command = model.name
        else:
            command = executableName
    else: 
        if executableName is None:
            command = executablePath + model.name
        else:
            command = executablePath + executableName
    return command
    
def get_galaxy_parameter_name(param_name):
    return "param_%s" % param_name
    
def create_inputs(doc, tool, model):
    inputs_node = doc.createElement("inputs")
    # treat all non output-file parameters as inputs
    for param in extract_parameters(model):
        if param.type is not _OutFile:
            inputs_node.appendChild(create_param_node(doc, param))
    tool.appendChild(inputs_node)
    
def create_param_node(doc, param):
    param_node = doc.createElement("param")
    param_node.setAttribute("name", get_galaxy_parameter_name(param.name))
    label = ""
    if param.description is not None:
        label = param.description
    else:
        label = "%s parameter" % param.name
    param_node.setAttribute("label", label)
    
    param_type = TYPE_TO_GALAXY_TYPE[param.type]
    if param_type is None:
        raise ModelError("Unrecognized parameter type '%(type)' for parameter '%(name)'" % {"type":param.type, "name":param.name})
    # galaxy handles ITEMLIST from CTDs as strings
    if param.is_list:
        param_type = "text"
        
    if is_boolean_parameter(param):
        param_type = "boolean"
        
    param_node.setAttribute("type", param_type)

    if param.type is _InFile:
        # assume it's just data unless restrictions are provided
        param_format = "data"
        if param.restrictions is not None:
            # join all supported_formats for the file... this MUST be a _FileFormat            
            if type(param.restrictions) is _FileFormat: 
                param_format = ','.join(param.restrictions.formats)
            else:
                raise InvalidModelException("Expected 'file type' restrictions for input file [%(name)s], but instead got [%(type)s]" % {"name":param.name, "type":type(param.restrictions)}) 
        param_node.setAttribute("format", param_format)
        param_type = "data"

    # check for parameters with restricted values (which will correspond to a "select" in galaxy)
    if param.restrictions is not None:
        # it could be either _Choices or _NumericRange, with special case for boolean types
        if param_type == "boolean":
            create_boolean_parameter(param, param_node)            
        elif type(param.restrictions) is _Choices:
            # create as many <option> elements as restriction values
            for choice in param.restrictions.choices:
                option_node = doc.createElement("option")
                option_node.setAttribute("value", str(choice))
                option_label = doc.createTextNode(str(choice))
                option_node.appendChild(option_label)
                param_node.appendChild(option_node)
        elif type(param.restrictions) is _NumericRange:
            if param.type is not int and param.type is not float:
                raise InvalidModelException("Expected either 'int' or 'float' in the numeric range restriction for parameter [%(name)s], but instead got [%(type)s]" % {"name":param.name, "type":type(param.restrictions)})
            # extract the min and max values and add them as attributes
            # validate the provided min and max values
            if param.restrictions.n_min is not None:
                param_node.setAttribute("min", str(param.restrictions.n_min))
            if param.restrictions.n_max is not None:
                param_node.setAttribute("max", str(param.restrictions.n_max))
        elif type(param.restrictions) is _FileFormat:
            param_node.setAttribute("format", ",".join(param.restrictions.formats))                     
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] for parameter [%(name)s]" % {"type":type(param.restrictions), "name":param.name}) 
    
    if param_type == "text":
        # add size attribute... this is the length of a textbox field in Galaxy (it could also be 15x2, for instance)
        param_node.setAttribute("size", "20")
    
    
    # check for default value
    if param.default is not None:
        if type(param.default) is list:
            # we ASSUME that a list of parameters looks like:
            # $ tool -ignore He Ar Xe
            # meaning, that, for example, Helium, Argon and Xenon will be ignored            
            param_node.setAttribute("value", ' '.join(param.default))        
        elif param_type != "boolean":
            # boolean parameters handle default values by using the "checked" attribute
            # there isn't much we can do... just stringify the value
            param_node.setAttribute("value", str(param.default))
    
    return param_node

# determines if the given choices are boolean (basically, if the possible values are yes/no, true/false)
def is_boolean_parameter(param):
    is_choices = False
    if type(param.restrictions) is _Choices:
        # for a true boolean experience, we need 2 values
        # and also that those two values are either yes/no or true/false
        if len(param.restrictions.choices) == 2:
            choices = get_lowercase_list(param.restrictions.choices)
            if ('yes' in choices and 'no' in choices) or ('true' in choices and 'false' in choices):
                is_choices = True
    return is_choices

def get_lowercase_list(some_list):
    lowercase_list = map(str, some_list)
    lowercase_list = map(string.lower, lowercase_list)
    lowercase_list = map(strip, lowercase_list)
    return lowercase_list

# creates a galaxy boolean parameter type
# this method assumes that param has restrictions, and that only two restictions are present (either yes/no or true/false)
def create_boolean_parameter(param, param_node):
    # first, determine the 'truevalue' and the 'falsevalue'
    truevalue = None
    falsevalue = None
    choices = get_lowercase_list(param.restrictions.choices)
    if "yes" in choices:
        truevalue = "yes"
        falsevalue = "no"        
    else:
        truevalue = "true"
        falsevalue = "false"    
    param_node.setAttribute("truevalue", truevalue)
    param_node.setAttribute("falsevalue", falsevalue)
    
    # set the checked attribute    
    if param.default is not None:
        checked_value = "false"
        default = strip(string.lower(param.default))
        if default == "yes" or default == "true":
            checked_value = "true"
        param_node.setAttribute("checked", checked_value)

def create_outputs(doc, tool, model):
    outputs_node = doc.createElement("outputs")
    for param in extract_parameters(model):
        if param.type is _OutFile:
            outputs_node.appendChild(create_data_node(doc, param))
    tool.appendChild(outputs_node) 

def create_data_node(doc, param):
    data_node = doc.createElement("data")
    data_node.setAttribute("name", get_galaxy_parameter_name(param.name))
    data_format = "data"
    if param.restrictions is not None:
        if type(param.restrictions) is _FileFormat:
            data_format = ','.join(param.restrictions.formats)            
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] for output [%(name)s]" % {"type":type(param.restrictions), "name":param.name})
    data_node.setAttribute("format", data_format)
    
    if param.description is not None:
        data_node.setAttribute("label", param.description)
        
    return data_node

def create_help(doc, tool, model):
    manual = None
    doc_url = None
    if 'manual' in model.opt_attribs.keys(): 
        model.opt_attribs["manual"]
    if 'docurl' in model.opt_attribs.keys():
        model.opt_attribs["docurl"]
    help_text = "No help available"
    if manual is not None:
        help_text = manual
    if doc_url is not None:
        help_text = ("" if manual is None else manual) + " For more information, visit %s" % doc_url
        
    help_node = doc.createElement("help")
    help_node.appendChild(doc.createTextNode(help_text))
    tool.appendChild(help_node)
    
# since a model might contain several ParameterGroup elements, we want to simply 'flatten' the parameters to generate the Galaxy wrapper    
def extract_parameters(model):
    parameters = []    
    if len(model.parameters.parameters) > 0:
        # use this to put parameters that are to be processed
        # we know that CTDModel has one parent ParameterGroup
        pending = [model.parameters]
        while len(pending) > 0:
            # take one element from 'pending'
            parameter = pending.pop()
            if type(parameter) is not ParameterGroup:
                parameters.append(parameter)
            else:
                # append the first-level children of this ParameterGroup
                pending.extend(parameter.parameters.values()) 
    # returned the reversed list of parameters (as it is now, we have the last parameter in the CTD as first in the list)
    return reversed(parameters)
    
class InvalidModelException(ModelError):
    def __init__(self, message):
        super(InvalidModelException, self).__init__()
        self.message = message

    def __str__(self):
        return self.message
    
    def __repr__(self):
        return self.message
        
if __name__ == "__main__":
    sys.exit(main())