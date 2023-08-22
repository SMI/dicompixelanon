## Pre-publishable version. Please report bugs/errors to gkaur001@dundee.ac.uk

## Library used for extracting DICOM tags
require("oro.dicom")

## Invisible DICOM reading and plotting machinery powering functions DIplot(), DItag() & DIcheck()
plot.mech = function(itc = i) {
  x = readDICOMFile(itc, flipud = F, pixelData = F)
  rgb = as.integer(unique(x$hdr$value[x$hdr$name == "SamplesperPixel"]))
  mf = ifelse("NumberOfFrames" %in% x$hdr$name, as.integer(x$hdr$value[x$hdr$name == "NumberOfFrames"]), 1)
  signed = ifelse(unique(x$hdr$value[x$hdr$name == "PixelRepresentation"]) == 1, T, F)
  if (rgb == 3) {
    fsize = file.info(itc)$size
    fraw = readBin(itc, "raw", n = as.integer(fsize))
    rows = as.integer(x$hdr$value[x$hdr$name == "Rows"])[1]
    columns = as.integer(x$hdr$value[x$hdr$name == "Columns"])[1]
    bytes = as.integer(x$hdr$value[x$hdr$name == "BitsAllocated"])[1]/8
    length = max(as.integer(x$hdr$length[x$hdr$name == "PixelData"]))
    skip = fsize - length + 1
    framesize = rows*columns*rgb*bytes
    for (frame in 1:mf) {
      imageData = readBin(fraw[(skip+((frame-1)*framesize)):fsize], "integer", n = length/mf, size = bytes, signed = signed, endian = "little")
      imageData = array(imageData[c(seq(1, length/mf, rgb), seq(2, length/mf, rgb), seq(3, length/mf, rgb))], c(columns, rows, rgb))
      imageData = aperm(imageData, c(2, 1, 3))
      plot(as.raster(imageData / 255))
      if (mf > 1) {print(paste("Frame#: ", frame, "/", mf))}
    } 
  } else {
    x = readDICOMFile(itc, flipud = F)
    if (mf == 1) {plot(as.raster(x$img / ifelse(signed, 255, max(x$img))))
    } else {
      for (frame in 1:mf) {
        y = x$img[,,frame]
        plot(as.raster(y/255))
        print(paste("Frame#: ", frame, "/", mf))
      }
    }
  }
}

## DIplot(): faster plotting for data exploration
DIplot = function(DICOMdir, # Root folder containing DICOMs or vector of relativefileURIs
                  recursive = F, # Plot DICOMs within sub-folders?
                  prompt = "next", # prompt for plotting next (on enter)
                  back = "<", # Reserved input for going back iteration(s) eg. < for 1, << for 2 and so on...
                  random = F) # Should the DICOMs be plotted in random order?
{
  if (any(file.exists(DICOMdir))) {
    f = DICOMdir[file.exists(DICOMdir) & endsWith(DICOMdir, ".dcm")]
  }
  if (dir.exists(DICOMdir)) {
    f = list.files(DICOMdir, full.names = T, recursive = recursive)
    f = f[endsWith(f, ".dcm")]
  }
  if (random) {f = sample(f)}
  l = ""
  for (i in f) {
    if (l != "" && unique(strsplit(l, "")[[1]]) == back) {
      fb = f[(which(f == i) - nchar(l) - 1):(which(f == i))]
      for (j in fb) {
        plot.mech(j)
        mtext(which(f == j), cex = 2)
        l = readline(prompt)
      }
    } else {
      plot.mech(i)
      mtext(which(f == i), cex = 2)
      l = readline(prompt)
    }
  }
}


## DItag(): plotting and tagging DICOMs in specified folder location. Output is a tagfile in .csv format
## Usage: tags = DItag(DICOMdir = "C:\\Users\\gkaur\\Desktop\\US_Anon") to save and retrieve output within R environment as tags in addition to tagfile on disk
DItag = function(DICOMdir, # Folder containing DICOMs to be labelled. A folder named "DONE" will be created within this location
                 resume = F, # TRUE if resuming previous task (example returning from a system crash)
                 DefaultTag = "No PII", # The most frequently expected tag
                 prompt = paste("Press Enter if", DefaultTag, "or type p for PII or type comment: ", sep = " "), 
                 saveToDir = DICOMdir, # Directory where output tagfile should be saved
                 filename = "tagfile", # Only name part of output file, it will be suffixed by .csv by default
                 random = F, # Should the DICOMs be plotted in random order?
                 progress = T, # "Are we there yet?"-prompt
                 interval = 10, # Progress prompt after how many DICOMs? To be used with progress = T else ignore
                 user = "Your Name", # username to be printed for signed datetime
                 back = "<") # Reserved input for going back iteration(s) eg. < for 1, << for 2 and so on.
{
  f = list.files(normalizePath(DICOMdir), full.names = T, recursive = F) 
  if (resume) {etagfile = read.csv(f[endsWith(f, paste("/", filename, ".csv", sep = ""))])}
  f = f[endsWith(f, ".dcm")]
  if (random) {f = sample(f)}
  doneDir = paste(DICOMdir, "DONE", sep = "/")
  dir.create(doneDir)
  print(paste(length(f), "DICOMs found... Begin image labelling :)", sep = " "))
  label = rep(NA, length(f))
  label_datetime = rep(NA, length(f))
  l = ""
  for (i in f) {
    if (l != "" && unique(strsplit(l, "")[[1]]) == back) {
      fb = f[(which(f == i) - nchar(l) - 1):(which(f == i))]
      for (j in fb) {
        file.copy(from = paste(paste(strsplit(fb[fb == j], "/")[[1]][1], "\\DONE", sep = ""), 
                               strsplit(fb[fb == j], "/")[[1]][2], sep = "/"), 
                  to = DICOMdir)
        plot.mech(j); mtext(label[f == j], cex = 2)
        l = readline(prompt)
        label[f == j] = ifelse(l == "", DefaultTag, ifelse(unique(strsplit(l, "")[[1]]) == back, NA, l))
        label_datetime[f == j] = paste("Tagged by", user, "at", Sys.time(), sep = " ")
        file.copy(from = j, to = doneDir, overwrite = T); file.remove(j)
      }  
    } else { 
      plot.mech(i); mtext(which(f == i), cex = 2)
      l = readline(prompt) 
      label[f == i] = ifelse(l == "", DefaultTag, ifelse(unique(strsplit(l, "")[[1]]) == back, NA, l))
      label_datetime[f == i] = paste("Tagged by", user, Sys.time(), sep = " ")
      file.copy(from = i, to = doneDir, overwrite = T); file.remove(i)
    }
    tagfile = data.frame(PK = f[!is.na(label)],
                         Label = label[!is.na(label)],
                         Label_datetime = label_datetime[!is.na(label)])
    if (resume) {tagfile = rbind.data.frame(etagfile[,-1], tagfile)}
    write.csv(tagfile, paste(saveToDir, "/", filename, ".csv", sep = ""))
    if (progress && nrow(tagfile) %% interval == 0) 
    {print(paste(nrow(tagfile), "/", length(f), "... ", round(nrow(tagfile)/(length(f))*100), "%", sep = ""))}
  }
  t = table(tagfile$Label, dnn = "Exit Summary:")
  print(t)
  barplot(t, main = "Exit Summary")
  return(tagfile)
}

## DIcheck(): Function for plotting and validating output from DItag() 
DIcheck = function(DICOMdir, #Location of the Tagged DICOMs/folder
                   tagfile = read.csv(paste(DICOMdir, "tagfile.csv", sep = "/")), # or object in global environment can also be called 
                   resume = F, # TRUE if returning from system crash or interval
                   startFrom = which(is.na(tagfile$Check_datetime))[1], #To be used with resume = T else ignore. Resumes from the first NA in Check_datetime by default
                   back = "<", # Reserved input for going back iteration(s)
                   user = "Your Name") # username to be printed for signed datetime
{
  if (is.object(tagfile) && is.data.frame(tagfile) && c("PK", "Label") %in% names(tagfile)) {
    if (resume && "Check_datetime" %in% names(tagfile)) {print("Using existing tag file...")} else {
      tagfile$Check_datetime = rep(NA, nrow(tagfile)) }
    lf = list.files(normalizePath(DICOMdir), full.names = T, recursive = T)
    lf = lf[endsWith(lf, ".dcm")]
    correction = ""
    for (i in tagfile$PK[ifelse(useExistingTagfile, startFrom, 1):length(tagfile$PK)]) {
      sid = strsplit(i, "/")[[1]][2]
      k = lf[endsWith(lf, sid)][1]
      if (correction != "" && unique(strsplit(correction, "")[[1]]) == back) {
        fb = tagfile$PK[(which(tagfile$PK == i) - nchar(correction) - 1):(which(tagfile$PK == i))]
        for (j in fb) {
          bsid = strsplit(j, "/")[[1]][2]
          j = lf[endsWith(lf, bsid)][1]
          plot.mech(j)
          mtext(tagfile$Label[endsWith(tagfile$PK, bsid)], cex = 2)
          correction = readline("Enter for next or type in correction: ")
          tagfile$Label[endsWith(tagfile$PK, bsid)] = ifelse(correction == "" || unique(strsplit(correction, "")[[1]]) == back, 
                                                             tagfile$Label[endsWith(tagfile$PK, bsid)], correction)
          tagfile$Check_datetime[endsWith(tagfile$PK, bsid)] = paste("Checked by", user, Sys.time(), sep = " ")
          write.csv(tagfile, paste(DICOMdir, "tagfile.csv", sep = "/"), row.names = F)
        }
      } else {
        plot.mech(k)
        mtext(tagfile$Label[tagfile$PK == i], cex = 2)
        correction = readline("Enter for next or type in correction: ")
        tagfile$Label[tagfile$PK == i] = ifelse(correction == "" || unique(strsplit(correction, "")[[1]]) == back, 
                                                tagfile$Label[tagfile$PK == i], correction)
        tagfile$Check_datetime[tagfile$PK == i] = paste("Checked by", user, Sys.time(), sep = " ")
        write.csv(tagfile, paste(DICOMdir, "tagfile.csv", sep = "/"), row.names = F)
      }
    }
    return(tagfile)} else {print("Invalid tagfile input")}
}

