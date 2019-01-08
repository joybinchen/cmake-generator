/**
 * -------------------------------------------------------------------------
 *                     The CodeChecker Infrastructure
 *   This file is distributed under the University of Illinois Open Source
 *   License. See LICENSE.TXT for details.
 * -------------------------------------------------------------------------
 */

#include "ldlogger-tool.h"
#include "ldlogger-util.h"

#include <sys/types.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>
#include <unistd.h>
#include <string.h>
/**
 * States for custom argument parser.
 */

#define PROG_LIST_SEPARATOR ":"

typedef enum _GccArgsState
{
  /**
   * Normal state (default).
   */
  Normal,
  /**
   * After a -o parameter.
   */
  InOutputArg,
  /**
   * After a plain option parameter. Don't recognize it as input or file.
   */
  InOptionArg,
} CustomArgsState;

/**
 * Reads a colon separated list from the given environment variable and tries
 * to match to the given argument. If one argument prefix matches (from the list)
 * to the given argument name, then it will return a non zero value.
 *
 * On any error or mismatch the function returns 0.
 *
 * @param argListVar_ the value of environment variable.
 * @param argument_ argument name to match.
 * @return position of the argument value on match, 0 otherwise
 */
static char* matchToArgList(
        const char* argListVar,
        const char* argument_)
{
  char* argList;
  char* token;
  char* pos;
  if (!argListVar)
  {
    return NULL;
  }

  argList = loggerStrDup(argListVar);
  if (!argList)
  {
    return NULL;
  }

  token = strtok(argList, PROG_LIST_SEPARATOR);
  while (token)
  {
    pos = strstr(argument_, token);
    if (pos)
    {
      /* Match! */
      pos += strlen(token);
      free(argList);
      return pos;
    }

    token = strtok(NULL, PROG_LIST_SEPARATOR);
  }

  free(argList);
  return NULL;
}

static char* findFullPath(const char* executable, char* fullpath) {
  char* path;
  char* dir;
  path = strdup(getenv("PATH"));
  for (dir = strtok(path, ":"); dir; dir = strtok(NULL, ":")) {
    strcpy(fullpath, dir);
    strcpy(fullpath + strlen(dir), "/");
    strcpy(fullpath + strlen(dir) + 1, executable);
    if (access(fullpath, F_OK ) != -1 ) {
        free(path);
        return fullpath;
    }
  }
  free(path);
  return 0;
}

static void normalizeToolName(char* str_)
{
  char *p = NULL;
  for (p = str_ + strlen(str_) - 1; p >= str_; --p) {
    if (!isalnum(*p))
    {
      *p = '_';
    }
  }
}

int loggerCustomParserCollectActions(
  const char* prog_,
  const char* toolName_,
  const char* const argv_[],
  LoggerVector* actions_)
{
  size_t i;
  /* Position of the last include path + 1 */
  char full_prog_path[PATH_MAX+1];
  static const char custom_output_env_prefix[] = "CC_LOGGER_OUTPUT_ARG_";
  static const char custom_option_env_prefix[] = "CC_LOGGER_OPTION_ARG_";
  char tool_name[100];
  char custom_env[100];
  char custom_arg_env[100];
  char *path_ptr;
  char* outputArgName;
  const char* argListVar;
  const char* optListVar;

  CustomArgsState state = Normal;
  LoggerAction* action = loggerActionNew(toolName_);

  strncpy(tool_name, toolName_, sizeof(tool_name) - 1);
  normalizeToolName(tool_name);

  strcpy(custom_env, custom_output_env_prefix);
  strncat(custom_env, tool_name, sizeof(custom_env) - 1);
  outputArgName= getenv(custom_env);
  if (outputArgName == NULL) return 0;

  strcpy(custom_arg_env, custom_output_env_prefix);
  strncat(custom_arg_env, tool_name, sizeof(custom_arg_env) - 1);
  argListVar = getenv(custom_arg_env);

  strcpy(custom_arg_env, custom_option_env_prefix);
  strncat(custom_arg_env, tool_name, sizeof(custom_arg_env) - 1);
  optListVar = getenv(custom_arg_env);

  /* If prog_ is a relative path we try to
   * convert it to absolute path.
   */
  path_ptr = realpath(prog_, full_prog_path);

  /* If we cannot convert it, we try to find the
   * executable in the PATH.
   */
  if (!path_ptr)
	  path_ptr = findFullPath(toolName_, full_prog_path);
  if (path_ptr) /* Log compiler with full path. */
	  loggerVectorAdd(&action->arguments, loggerStrDup(full_prog_path));
  else  /* Compiler was not found in path, log the binary name only. */
  	  loggerVectorAdd(&action->arguments, loggerStrDup(toolName_));

  for (i = 1; argv_[i]; ++i)
  {
    const char* arg_ = argv_[i];
    char argToAdd[PATH_MAX];
    strcpy(argToAdd, arg_);
    if (state == InOptionArg)
    {
      state = Normal;
    }
    else if (state == Normal)
    {
      char *pos = matchToArgList(optListVar, argToAdd);
      if (pos == NULL)
      {
        char *pos = matchToArgList(argListVar, argToAdd);
        if (pos == NULL)
        {
          if (arg_[0] != '-') {
            char fullPath[PATH_MAX];
            if (loggerMakePathAbs(arg_, fullPath, 0)) {
              strcpy(argToAdd, fullPath);
              loggerVectorAddUnique(&action->sources, loggerStrDup(fullPath),
                                    (LoggerCmpFuc) &strcmp);
              if (argListVar[0] == '$'
                  && strtol(argListVar+1, NULL, 10) == action->sources.size)
                loggerFileInitFromPath(&action->output, fullPath);
            }
          }
        }
        else if (*pos == 0)
        {
          state =InOutputArg;
        }
        else if (*pos == '=')
        {
          char fullPath[PATH_MAX];
          if (loggerMakePathAbs(pos + 1, fullPath, 0))
          {
            loggerFileInitFromPath(&action->output, fullPath);
            pos[1] = 0;
            strcat(argToAdd, fullPath);
          }
        }
      }
      else if (*pos == 0)
      {
        state =InOptionArg;
      }
    }
    else /* if (state == InOutputArg) */
    {
      char fullPath[PATH_MAX];
      if (loggerMakePathAbs(arg_, fullPath, 0))
      {
        strcpy(argToAdd, fullPath);
        loggerFileInitFromPath(&action->output, fullPath);
      }
      state = Normal;
    }
    if (argToAdd[0]) {
      loggerVectorAdd(&action->arguments, loggerStrDup(argToAdd));
    }
  }

  if (argListVar[0] == '$')
  {
    char* end_pos;
    long output_pos = strtol(argListVar+1, &end_pos, 10);
    if (output_pos < 0) {
      output_pos += action->sources.size;
      if (output_pos >= 0) {
        loggerFileInitFromPath(&action->output, action->sources.data[output_pos]);
        /*loggerVectorErase(&action->sources, output_pos);*/
      }
    }
  }

  /*
   * Workaround for -MT and friends: if the source set contains the output,
   * then we have to remove it from the set.
   */
  i = loggerVectorFind(&action->sources, action->output.path,
    (LoggerCmpFuc) &strcmp);
  if (i != SIZE_MAX)
  {
    loggerVectorErase(&action->sources, i);
  }

  if (action->sources.size != 0)
    loggerVectorAdd(actions_, action);

  return 1;
}
